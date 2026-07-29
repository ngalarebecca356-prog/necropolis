from ninja import NinjaAPI, Schema
from ninja import Schema
from ninja.security import HttpBearer
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse as DjangoResponse
from typing import List, Optional
import random
from datetime import timedelta
from django.utils import timezone
import secrets
import folium
from datetime import date
from .models import Caveau, Defunt, Reservation, Concession, Exhumation, Profil, AuditLog, Cimetiere, SessionToken, Transaction


class TokenAuth(HttpBearer):
    """
    Authentification par jeton simple. Le client Flet envoie
    `Authorization: Bearer <cle>` obtenu après vérification du code MFA.
    Sans jeton valide, request.auth est None et request.user reste anonyme.
    """
    def authenticate(self, request, token):
        try:
            st = SessionToken.objects.select_related('utilisateur').get(cle=token)
        except SessionToken.DoesNotExist:
            return None
        request.user = st.utilisateur
        return st.utilisateur


token_auth = TokenAuth()

api = NinjaAPI(title="NECROPOLIS API", version="2026.1")
codes_mfa = {}


def profil_de(request):
    """Renvoie le Profil de l'utilisateur authentifié via le jeton, ou None."""
    user = getattr(request, 'auth', None)
    if not user:
        return None
    return getattr(user, 'profil', None)


def cimetiere_de(request):
    """Récupère le cimetière de l'utilisateur connecté de manière sécurisée"""
    user = request.auth
    if not user:
        return None
    
    from gestion.models import Cimetiere
    
    # Si l'utilisateur est admin, récupérer SON cimetière (le premier trouvé, sans planter)
    if hasattr(user, 'profil') and user.profil.role == 'admin':
        return Cimetiere.objects.filter(admin_createur=user).first()
    
    # Si c'est un agent/secrétaire, récupérer le cimetière via son profil
    if hasattr(user, 'profil') and getattr(user.profil, 'cimetiere', None):
        return user.profil.cimetiere
    
    return None


def role_de(request):
    """Renvoie le role (str) de l'utilisateur authentifié, ou None."""
    profil = profil_de(request)
    return profil.role if profil else None


def refuser_si_role_absent(request, roles_autorises):
    """
    Renvoie une reponse 403 si le role de l'utilisateur n'est pas dans
    roles_autorises, sinon renvoie None (acces autorise).
    """
    if role_de(request) not in roles_autorises:
        return api.create_response(
            request,
            {"error": "Acces refuse — role insuffisant pour cette action"},
            status=403,
        )
    return None

# ═══════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════
class LoginSchema(Schema):
    username: str
    password: str

class VerifySchema(Schema):
    email: str
    code: str

class RegisterSchema(Schema):
    username: str
    email: str
    password: str
    role: str
    nom: str = ""          # <-- AJOUTE CECI
    prenom: str = ""
    
    telephone: str = ""       # <-- AJOUTÉ
    photo: str = ""           # <-- AJOUTÉ
    # ── Rattachement à un cimetière ──
    mode: Optional[str] = None                             # "creer" ou "rejoindre"
    nom_cimetiere: Optional[str] = ""
    mot_de_passe_cimetiere: Optional[str] = ""
    ville: Optional[str] = ""
    quartier: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # AJOUTE CES 4 LIGNES 
    limite_nord: Optional[float] = None
    limite_sud: Optional[float] = None
    limite_est: Optional[float] = None
    limite_ouest: Optional[float] = None
    superficie_totale: Optional[float] = 0
    tombeau_longueur: Optional[float] = 2.5
    tombeau_largeur: Optional[float] = 1.2

class CreerMembreSchema(Schema):
    username: str
    email: str
    password: str
    role: str  # 'agent' ou 'secretariat'
    nom: str = ""
    prenom: str = ""
    telephone: str = ""

class CaveauOut(Schema):
    id: int
    numero: str
    section: str
    bloc: str
    statut: str

class DefuntOut(Schema):
    id: int
    nom: str
    prenom: str
    date_deces: date
    caveau_id: Optional[int]

class PaiementSimuleSchema(Schema):
    reservation_id: int
    methode: str
    numero_telephone: str = ""
    montant: Optional[float] = None 

# ══════════════════════════════════════════════════
# AUTHENTIFICATION — MFA DIRECT (pas de validation admin)
# ═══════════════════════════════════════════════════
@api.post("/auth/register")
def register(request, data: RegisterSchema):
    if User.objects.filter(username=data.username).exists():
        return api.create_response(request, {"error": "Ce nom d'utilisateur existe deja"}, status=400)
    if User.objects.filter(email=data.email).exists():
        return api.create_response(request, {"error": "Cet email est deja utilise"}, status=400)
    if data.role not in ['admin', 'agent', 'secretariat', 'client']:
        return api.create_response(request, {"error": "Role invalide"}, status=400)

    cimetiere = None

    # ── Si ce n'est PAS un client, le cimetière est OBLIGATOIRE ──
    if data.role != 'client':
        if not data.mode or data.mode not in ['creer', 'rejoindre']:
            return api.create_response(request, {"error": "Choisissez de creer ou rejoindre un cimetiere"}, status=400)
        if not data.nom_cimetiere.strip() or not data.mot_de_passe_cimetiere:
            return api.create_response(request, {"error": "Nom du cimetiere et mot de passe requis"}, status=400)

        if data.mode == "creer":
            if Cimetiere.objects.filter(nom__iexact=data.nom_cimetiere.strip()).exists():
                return api.create_response(request, {"error": "Ce nom de cimetiere est deja pris"}, status=400)
            if len(data.mot_de_passe_cimetiere) < 4:
                return api.create_response(request, {"error": "Mot de passe du cimetiere trop court"}, status=400)

         # 1. Vérifier la taille du cimetière
            if data.limite_nord and data.limite_sud and data.limite_est and data.limite_ouest:
                # Calculer la superficie approximative
                largeur = abs(data.limite_est - data.limite_ouest) * 111000  # Conversion en mètres
                hauteur = abs(data.limite_nord - data.limite_sud) * 111000
                superficie_calculee = largeur * hauteur
                
                # Vérifier si c'est trop grand (max 20000 m²)
                if superficie_calculee > 20000:
                    return api.create_response(request, {
                        "error": f"Le cimetière est trop grand ({superficie_calculee:.0f} m²). "
                                 f"La taille maximale autorisée est 20000 m². "
                                 f"Vérifiez les limites sur la carte."
                    }, status=400)
                
                # Vérifier si c'est trop petit (min 500 m²)
                if superficie_calculee < 500:
                    return api.create_response(request, {
                        "error": f"Le cimetière est trop petit ({superficie_calculee:.0f} m²). "
                                 f"La taille minimale est 500 m²."
                    }, status=400)
            
            # 2. Vérifier la cohérence quartier/ville
            quartiers_valides = {
                "Pointe-Noire": ["Lumumba", "Vindoulou", "Mvou-Mvou", "Tié-Tié", "Loandjili"],
                "Brazzaville": ["Ouenzé", "Makélékélé", "Bacongo", "Poto-Poto", "Centre Ville"],
            }
            
            if data.ville and data.quartier:
                ville_lower = data.ville.lower()
                quartier_lower = data.quartier.lower()
                
                if ville_lower in quartiers_valides:
                    quartiers_de_la_ville = [q.lower() for q in quartiers_valides[ville_lower]]
                    if quartier_lower not in quartiers_de_la_ville:
                        return api.create_response(request, {
                            "error": f"Le quartier '{data.quartier}' n'existe pas à {data.ville}. "
                                     f"Quartiers valides : {', '.join(quartiers_valides[ville_lower])}. "
                                     f"Vérifiez la position sur la carte."
                        }, status=400)
            
            # 3. Vérifier si les limites sont cohérentes
            if data.limite_nord and data.limite_sud:
                if data.limite_nord <= data.limite_sud:
                    return api.create_response(request, {
                        "error": "La limite Nord doit être supérieure à la limite Sud. "
                                 "Vérifiez les coordonnées sur la carte."
                    }, status=400)
            
            if data.limite_est and data.limite_ouest:
                if data.limite_est <= data.limite_ouest:
                    return api.create_response(request, {
                        "error": "La limite Est doit être supérieure à la limite Ouest. "
                                 "Vérifiez les coordonnées sur la carte."
                    }, status=400)
                    
            cimetiere = Cimetiere.objects.create(
                nom=data.nom_cimetiere.strip(),
                ville=data.ville or "",
                quartier=data.quartier or "",
                pays="République du Congo",
                latitude=data.latitude,
                longitude=data.longitude,
                limite_nord=data.limite_nord,
                limite_sud=data.limite_sud,
                limite_est=data.limite_est,
                limite_ouest=data.limite_ouest,
                superficie_totale=data.superficie_totale or 0,
                tombeau_longueur=data.tombeau_longueur or 2.5,
                tombeau_largeur=data.tombeau_largeur or 1.2,
                mot_de_passe_acces=make_password(data.mot_de_passe_cimetiere),
            )
            cimetiere.nombre_places_estime = cimetiere.calculer_places()
            cimetiere.save()
        else:  # rejoindre
            cimetiere = Cimetiere.objects.filter(nom__iexact=data.nom_cimetiere.strip()).first()
            if not cimetiere:
                return api.create_response(request, {"error": "Aucun cimetiere ne porte ce nom"}, status=404)
            if not check_password(data.mot_de_passe_cimetiere, cimetiere.mot_de_passe_acces):
                return api.create_response(request, {"error": "Mot de passe d'acces au cimetiere incorrect"}, status=403)

    # ── Création de l'utilisateur (fonctionne pour TOUS les rôles) ──
    user = User.objects.create_user(username=data.username, email=data.email, password=data.password)
    profil = user.profil
    profil.role = data.role
    profil.cimetiere = cimetiere  # Sera None pour un client
    profil.statut = 'valide'
    profil.ville = data.ville or ""  # On sauvegarde la ville (utile pour le client)
    profil.nom = data.nom
    profil.prenom = data.prenom
    
    profil.telephone = data.telephone  # <-- AJOUTÉ
    profil.photo = data.photo          # <-- AJOUTÉ
    profil.save()

    if data.mode == "creer" and cimetiere:
        cimetiere.admin_createur = user
        cimetiere.save()

    # ── Notification par email ──
    try:
        nom_cimetiere_msg = cimetiere.nom if cimetiere else "Aucun (Compte Client)"
        send_mail(
            'NECROPOLIS - Nouvelle inscription',
            f'Nouvelle inscription :\n\n'
            f'Utilisateur : {data.username}\n'
            f'Email : {data.email}\n'
            f'Role : {data.role}\n'
            f'Cimetiere : {nom_cimetiere_msg}\n\n'
            f'Ce compte est deja actif.',
            settings.DEFAULT_FROM_EMAIL,
            ['ngalarebecca356@gmail.com']
        )
    except:
        pass

    return {
        "message": "Inscription reussie. Vous pouvez vous connecter immediatement.", 
        "cimetiere": cimetiere.nom if cimetiere else None
    }

@api.post("/auth/login")
def login_mfa(request, data: LoginSchema):
    login = data.username.strip()
    user_obj = User.objects.filter(email__iexact=login).first() if "@" in login else None
    username = user_obj.username if user_obj else login
    user = authenticate(username=username, password=data.password)
    
    if not user:
        return api.create_response(request, {"error": "Identifiants invalides"}, status=401)
    if not user.email:
        return api.create_response(request, {"error": "Pas d'email configure"}, status=400)
    
    code = str(random.randint(100000, 999999))
    codes_mfa[user.email] = code
    codes_mfa[user.email + "_user"] = user.id
    
    try:
        send_mail(
            'NECROPOLIS - Code de verification',
            f'Votre code MFA : {code}\n\nCe code expire dans 10 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
    except Exception as e:
        print(f"Erreur email : {e}")
    
    return {
        "step": "mfa_required",
        "email": user.email,
        "debug_code": code
    }

@api.post("/auth/verify")
def verify_mfa(request, data: VerifySchema):
    if codes_mfa.get(data.email) == data.code:
        codes_mfa.pop(data.email, None)
        codes_mfa.pop(data.email + "_user", None)
        user = User.objects.get(email=data.email)
        profil = getattr(user, 'profil', None)

        # Un seul jeton actif par utilisateur : on remplace l'ancien.
        SessionToken.objects.filter(utilisateur=user).delete()
        cle = secrets.token_hex(32)
        SessionToken.objects.create(utilisateur=user, cle=cle)

        return {
            "token": cle,
            "user": user.username,
            "role": profil.role if profil else "client",
            "statut": profil.statut if profil else "valide",
            "cimetiere": profil.cimetiere.nom if (profil and profil.cimetiere) else None,
        }
    return api.create_response(request, {"error": "Code invalide"}, status=400)

# ═══════════════════════════════════════════════════
# GESTION D'ÉQUIPE (réservé à l'administrateur du cimetière)
# ═══════════════════════════════════════════════════
@api.post("/users/creer", auth=token_auth)
def creer_membre(request, data: CreerMembreSchema):
    refus = refuser_si_role_absent(request, ['admin'])
    if refus:
        return refus
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return api.create_response(request, {"error": "Aucun cimetiere associe a ce compte"}, status=403)
    if data.role not in ['agent', 'secretariat']:
        return api.create_response(request, {"error": "Role invalide — utilisez agent ou secretariat"}, status=400)
    if User.objects.filter(username=data.username).exists():
        return api.create_response(request, {"error": "Ce nom d'utilisateur existe deja"}, status=400)
    if User.objects.filter(email=data.email).exists():
        return api.create_response(request, {"error": "Cet email est deja utilise"}, status=400)

    user = User.objects.create_user(username=data.username, email=data.email, password=data.password)
    profil = user.profil
    profil.role = data.role
    profil.cimetiere = cimetiere
    profil.statut = 'valide'
    profil.nom = data.nom
    profil.prenom = data.prenom
    profil.telephone = data.telephone
    profil.save()

    AuditLog.objects.create(
        utilisateur=request.user,
        action="Creation membre equipe",
        objet_type="User",
        objet_id=user.id,
        details=f"{data.username} ({data.role}) ajoute a {cimetiere.nom}"
    )
    return {"id": user.id, "ok": True}

@api.get("/users", auth=token_auth)
def lister_membres(request):
    refus = refuser_si_role_absent(request, ['admin'])
    if refus:
        return refus
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return []
    membres = Profil.objects.filter(cimetiere=cimetiere).select_related('user').order_by('-date_creation')
    return [
        {
            "id": p.user.id,
            "username": p.user.username,
            "email": p.user.email,
            "role": p.role,
            "statut": p.statut,
            "date_creation": p.date_creation.isoformat(),
        }
        for p in membres
    ]

# ═══════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════
@api.get("/dashboard/stats", auth=token_auth)
def stats(request):
    refus = refuser_si_role_absent(request, ['admin', 'agent', 'secretariat'])
    if refus:
        return refus
    cimetiere = cimetiere_de(request)
    role = role_de(request)
    caveaux_qs = Caveau.objects.filter(cimetiere=cimetiere) if cimetiere else Caveau.objects.none()
    
    # Imports pour les calculs de dates
    from datetime import timedelta
    from django.utils import timezone
    
    data = {
        "cimetiere": cimetiere.nom if cimetiere else None,
        "caveaux": caveaux_qs.count(),
        "disponibles": caveaux_qs.filter(statut='disponible').count(),
        "reserves": caveaux_qs.filter(statut='reserve').count(),
        "occupes": caveaux_qs.filter(statut='occupe').count(),
        "defunts": Defunt.objects.filter(caveau__cimetiere=cimetiere).count() if cimetiere else 0,
        "reservations": Reservation.objects.filter(caveau__cimetiere=cimetiere).count() if cimetiere else 0,
        "concessions": Concession.objects.filter(caveau__cimetiere=cimetiere).count() if cimetiere else 0,
        "exhumations": Exhumation.objects.filter(defunt__caveau__cimetiere=cimetiere).count() if cimetiere else 0,
    }
    
    # ═══════════════════════════════════════════════════
    # ALERTES PROFESSIONNELLES (Nouveau)
    # ═══════════════════════════════════════════════════
    today = timezone.now().date()
    six_mois_plus_tard = today + timedelta(days=180)
    
    # Concessions qui expirent dans les 6 prochains mois
    concessions_alerte = Concession.objects.filter(
        caveau__cimetiere=cimetiere, 
        date_fin__lte=six_mois_plus_tard, 
        date_fin__gte=today
    ).count() if cimetiere else 0
    
    # Exhumations en attente de validation
    exhumations_attente = Exhumation.objects.filter(
        defunt__caveau__cimetiere=cimetiere, 
        statut='demande'
    ).count() if cimetiere else 0
    
    data.update({
        "concessions_a_renouveler": concessions_alerte,
        "exhumations_en_attente": exhumations_attente
    })
    
    # Statistiques financières — reservees a l'administrateur (2.1 du cahier des charges)
    if role == 'admin' and cimetiere:
        from django.db.models import Sum
        total_concessions = Concession.objects.filter(
            caveau__cimetiere=cimetiere
        ).aggregate(total=Sum('montant'))['total'] or 0
        data["revenus_total"] = float(total_concessions)
    
    return data
# ═══════════════════════════════════════════════════
# CAVEAUX
# ═══════════════════════════════════════════════════
@api.get("/caveaux", response=List[CaveauOut], auth=token_auth)
def list_caveaux(request, statut: Optional[str] = None):
    cimetiere = cimetiere_de(request)
    qs = Caveau.objects.filter(cimetiere=cimetiere) if cimetiere else Caveau.objects.none()
    if statut:
        qs = qs.filter(statut=statut)
    return qs[:300]

from ninja import Schema  # ← Vérifie que c'est importé en haut

class CaveauCreateSchema(Schema):
    numero: str
    section: str
    bloc: str
    statut: str = 'disponible'

@api.post("/caveaux", auth=token_auth)
def create_caveau(request, data: CaveauCreateSchema):
    refus = refuser_si_role_absent(request, ['admin', 'agent'])
    if refus:
        return refus
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return api.create_response(request, {"error": "Aucun cimetiere associe a ce compte"}, status=403)
    
    c = Caveau.objects.create(
        cimetiere=cimetiere, 
        numero=data.numero, 
        section=data.section, 
        bloc=data.bloc, 
        statut=data.statut
    )
    AuditLog.objects.create(
        utilisateur=request.user,
        action="Creation caveau",
        objet_type="Caveau",
        objet_id=c.id,
        details=f"Caveau {data.numero} cree dans {cimetiere.nom}"
    )
    return {"id": c.id, "ok": True}

# ═══════════════════════════════════════════════════
# DEFUNTS
# ═══════════════════════════════════════════════════
@api.get("/defunts", response=List[DefuntOut], auth=token_auth)
def list_defunts(request, q: str = None):
    cimetiere = cimetiere_de(request)
    qs = Defunt.objects.filter(caveau__cimetiere=cimetiere).order_by('-date_deces') if cimetiere else Defunt.objects.none()
    if q:
        qs = qs.filter(nom__icontains=q)
    return qs[:200]

@api.post("/defunts", auth=token_auth)
def create_defunt(request, nom: str, prenom: str, date_deces: date, caveau_id: int = None):
    cimetiere = cimetiere_de(request)
    if caveau_id and not Caveau.objects.filter(id=caveau_id, cimetiere=cimetiere).exists():
        return api.create_response(request, {"error": "Caveau introuvable dans votre cimetiere"}, status=404)
    d = Defunt.objects.create(nom=nom, prenom=prenom, date_deces=date_deces, caveau_id=caveau_id)
    if caveau_id:
        Caveau.objects.filter(id=caveau_id).update(statut='occupe')
    return {"id": d.id}

# ═══════════════════════════════════════════════════
# RESERVATIONS
# ═══════════════════════════════════════════════════
@api.get("/reservations", auth=token_auth)
def list_reservations(request):
    cimetiere = cimetiere_de(request)
    qs = Reservation.objects.filter(caveau__cimetiere=cimetiere) if cimetiere else Reservation.objects.none()
    res_list = []
    for r in qs.select_related('caveau', 'client', 'defunt')[:100]:
        res_list.append({
            "id": r.id,
            "statut": r.statut,
            "date_reservation": r.date_reservation.isoformat() if r.date_reservation else None,
            "caveau_id": r.caveau.id,
            "caveau_numero": r.caveau.numero,
            "client": r.client.username,
            "nom_defunt": r.defunt.nom if r.defunt else "Non precise",
            "prenom_defunt": r.defunt.prenom if r.defunt else "",
        })
    return res_list

class ReservationCreateSchema(Schema):
    caveau_id: int
    nom_defunt: str
    prenom_defunt: str
    date_deces: date
    
    # Infos du client (optionnel - si vide, on utilise l'utilisateur connecté)
    client_nom: Optional[str] = None
    client_prenom: Optional[str] = None
    client_email: Optional[str] = None
    client_telephone: Optional[str] = None

@api.post("/reservations", auth=token_auth)
def create_reservation(request, data: ReservationCreateSchema):
    # Validation de la date
    from datetime import datetime
    if data.date_deces > datetime.now().date():
        return api.create_response(request, {"error": "La date de décès ne peut pas être dans le futur !"}, status=400)

    cimetiere = cimetiere_de(request)
    caveau = Caveau.objects.filter(id=data.caveau_id, cimetiere=cimetiere).first()
    if not caveau:
        return api.create_response(request, {"error": "Caveau introuvable"}, status=404)
    
    # Créer le défunt
    defunt = Defunt.objects.create(
        nom=data.nom_defunt, 
        prenom=data.prenom_defunt, 
        date_deces=data.date_deces, 
        caveau=caveau
    )
    
    # Déterminer le statut et les infos client
    user_role = role_de(request)
    
    if user_role == 'client':
        # Client qui réserve pour lui-même
        statut = 'en_attente'
        client_nom = request.user.first_name or request.user.username
        client_prenom = ""
        client_email = request.user.email
        client_telephone = ""
    else:
        # Admin/Secrétaire qui réserve pour un tiers
        statut = 'validee'  # Validation automatique
        client_nom = data.client_nom or ""
        client_prenom = data.client_prenom or ""
        client_email = data.client_email or ""
        client_telephone = data.client_telephone or ""
    
    # Créer la réservation
    reservation = Reservation.objects.create(
        caveau=caveau,
        client=request.user,  # Qui a fait la réservation
        defunt=defunt,
        statut=statut,
        client_nom=client_nom,
        client_prenom=client_prenom,
        client_email=client_email,
        client_telephone=client_telephone,
        cree_par=request.user,
        montant_total=150
    )
    
    caveau.statut = 'reserve'
    caveau.save()
    
    # Si client : envoyer notification d'attente
    if user_role == 'client':
        try:
            send_mail(
                'NECROPOLIS - Réservation en attente',
                f'Bonjour {client_nom},\n\n'
                f'Votre réservation pour le caveau N°{caveau.numero} a été enregistrée.\n'
                f'Elle est en attente de validation par notre équipe.\n'
                f'Vous recevrez un email de confirmation dès validation.\n\n'
                f'Cordialement,\nNECROPOLIS',
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                fail_silently=True,
            )
        except:
            pass
    
    # Si admin/secrétaire : validation auto + email au client
    else:
        reservation.valide_par = request.user
        reservation.date_validation = datetime.now()
        reservation.save()
        
        # Email de confirmation au client
        if client_email:
            try:
                send_mail(
                    'NECROPOLIS - Réservation confirmée',
                    f'Bonjour {client_nom} {client_prenom},\n\n'
                    f'Votre réservation pour le caveau N°{caveau.numero} a été VALIDÉE.\n'
                    f'Veuillez procéder au paiement pour confirmer votre réservation.\n\n'
                    f'Réservation enregistrée par : {request.user.username}\n\n'
                    f'Cordialement,\nNECROPOLIS',
                    settings.DEFAULT_FROM_EMAIL,
                    [client_email],
                    fail_silently=True,
                )
            except:
                pass
    
    return {"id": reservation.id, "ok": True, "statut": statut}

@api.put("/reservations/{rid}/valider", auth=token_auth)
def valider_reservation(request, rid: int):
    from datetime import datetime  # ← AJOUTE CETTE LIGNE
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus:
        return refus
    
    reservation = Reservation.objects.filter(id=rid).select_related('caveau', 'client', 'defunt').first()
    if not reservation:
        return api.create_response(request, {"error": "Réservation introuvable"}, status=404)
    
    # Validation
    reservation.statut = 'validee'
    reservation.valide_par = request.user
    reservation.date_validation = datetime.now()
    reservation.save()
    
    # Email au client
    client_email = reservation.client_email or reservation.client.email
    try:
        send_mail(
            'NECROPOLIS - Réservation validée',
            f'Bonjour {reservation.client_nom},\n\n'
            f'Votre réservation pour le caveau N°{reservation.caveau.numero} a été VALIDÉE.\n'
            f'Veuillez procéder au paiement.\n\n'
            f'Validée par : {request.user.username}\n'
            f'NECROPOLIS',
            settings.DEFAULT_FROM_EMAIL,
            [client_email],
            fail_silently=True,
        )
    except:
        pass
    
    return {"ok": True}

@api.get("/reservations/{rid}/facture", auth=token_auth)
def facture_reservation(request, rid: int):
    from .facture import generer_facture
    cimetiere = cimetiere_de(request)
    r = Reservation.objects.select_related('caveau', 'client', 'defunt').filter(id=rid, caveau__cimetiere=cimetiere).first()
    if not r:
        return api.create_response(request, {"error": "Reservation introuvable dans votre cimetiere"}, status=404)
    buffer = generer_facture(r)
    response = DjangoResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{rid}.pdf"'
    return response

# ═══════════════════════════════════════════════════
# CONCESSIONS
# ═══════════════════════════════════════════════════
@api.get("/concessions", auth=token_auth)
def liste_concessions(request):
    """Renvoie la liste des concessions avec tous les détails"""
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return []
    
    try:
        qs = Concession.objects.filter(caveau__cimetiere=cimetiere).select_related('caveau', 'client')
        
        data = []
        for c in qs:
            data.append({
                "id": c.id,
                "type_concession": c.type_concession,
                "caveau_id": c.caveau.id,
                "caveau_numero": c.caveau.numero,
                "date_debut": c.date_debut.strftime("%Y-%m-%d") if c.date_debut else "",
                "date_fin": c.date_fin.strftime("%Y-%m-%d") if c.date_fin else "Perpétuelle",
                "montant": float(c.montant) if c.montant else 0,
                "beneficiaire": c.beneficiaire or "Non spécifié",
            })
        return data
    except Exception as e:
        print(f"❌ ERREUR API CONCESSIONS: {e}")
        return []

class ConcessionCreateSchema(Schema):
    caveau_id: int
    type_concession: str
    date_debut: date
    date_fin: Optional[date] = None

@api.post("/concessions", auth=token_auth)
def create_concession(request, data: ConcessionCreateSchema):
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus:
        return refus
    
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return {"error": "Aucun cimetiere"}, 404
    
    # VÉRIFICATION 1 : Le caveau existe-t-il dans ce cimetière ?
    caveau = Caveau.objects.filter(id=data.caveau_id, cimetiere=cimetiere).first()
    if not caveau:
        return {"error": "Caveau introuvable dans votre cimetiere"}, 404
    
    # VÉRIFICATION 2 : Le caveau a-t-il déjà une concession ACTIVE ?
    concession_existante = Concession.objects.filter(
        caveau=caveau,
        date_fin__isnull=True  # Perpétuelle
    ).first() or Concession.objects.filter(
        caveau=caveau,
        date_fin__gt=timezone.now().date()  # Pas encore expirée
    ).first()
    
    if concession_existante:
        return {
            "error": "Ce caveau a déjà une concession active",
            "concession_id": concession_existante.id,
            "date_fin": concession_existante.date_fin.strftime("%Y-%m-%d") if concession_existante.date_fin else "Perpétuelle"
        }, 409  # 409 = Conflict
    
    # CALCUL AUTOMATIQUE de la date de fin selon le type
    from datetime import timedelta
    date_debut = data.date_debut
    if data.type_concession == "temporaire":
        date_fin = date_debut + timedelta(days=5*365)  # 5 ans
        montant = 300000
    elif data.type_concession == "trentenaire":
        date_fin = date_debut + timedelta(days=30*365)  # 30 ans
        montant = 1500000
    elif data.type_concession == "perpetuelle":
        date_fin = None  # Null = perpétuelle
        montant = 7500000
    else:
        return {"error": "Type de concession invalide"}, 400
    
    # CRÉATION de la concession
    c = Concession.objects.create(
        caveau=caveau,
        client=request.user,
        type_concession=data.type_concession,
        date_debut=date_debut,
        date_fin=date_fin,
        montant=montant,
        beneficiaire=data.beneficiaire or f"{request.user.first_name} {request.user.last_name}".strip()
    )
    
    # Le caveau passe en statut "occupe"
    caveau.statut = "occupe"
    caveau.save()
    
    # NOTIFICATION SMS/EMAIL au client
    envoyer_notification_concession(c, request.user)
    
    return {"id": c.id, "date_fin": date_fin.strftime("%Y-%m-%d") if date_fin else "Perpétuelle", "montant": montant, "ok": True}

@api.post("/concessions/{cid}/renouveler", auth=token_auth)
def renouveler_concession(request, cid: int):
    """Renouvelle une concession existante (prolonge la date de fin)"""
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus:
        return refus
    
    concession = Concession.objects.filter(id=cid).select_related('caveau').first()
    if not concession:
        return {"error": "Concession introuvable"}, 404
    
    # Vérifier que c'est bien le cimetière de l'utilisateur
    if concession.caveau.cimetiere != cimetiere_de(request):
        return {"error": "Accès non autorisé"}, 403
    
    # Calculer la nouvelle date de fin
    from datetime import timedelta
    if concession.type_concession == "temporaire":
        nouvelle_date = concession.date_fin + timedelta(days=5*365) if concession.date_fin else timezone.now().date() + timedelta(days=5*365)
        montant_renouvellement = 300000
    elif concession.type_concession == "trentenaire":
        nouvelle_date = concession.date_fin + timedelta(days=30*365) if concession.date_fin else timezone.now().date() + timedelta(days=30*365)
        montant_renouvellement = 1500000
    else:
        return {"error": "Une concession perpétuelle ne peut être renouvelée"}, 400
    
    # Mettre à jour
    concession.date_fin = nouvelle_date
    concession.save()
    
    # Notification
    envoyer_notification_renouvellement(concession, nouvelle_date, montant_renouvellement)
    
    return {"id": concession.id, "nouvelle_date_fin": nouvelle_date.strftime("%Y-%m-%d"), "montant": montant_renouvellement, "ok": True}

# ═══════════════════════════════════════════════════
# EXHUMATIONS
# ═══════════════════════════════════════════════════
class ExhumationCreateSchema(Schema):
    defunt_id: int
    motif: str

class ExhumationCreateSchema(Schema):
    defunt_id: int
    motif: str
    document_legal: str  # URL ou référence du document
    date_souhaitee: Optional[date] = None

@api.post("/exhumations", auth=token_auth)
def create_exhumation(request, data: ExhumationCreateSchema):
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return {"error": "Aucun cimetiere"}, 404
    
    defunt = Defunt.objects.filter(id=data.defunt_id, caveau__cimetiere=cimetiere).first()
    if not defunt:
        return {"error": "Défunt introuvable dans votre cimetiere"}, 404
    
    # VÉRIFICATION : Y a-t-il déjà une demande en attente pour ce défunt ?
    demande_existante = Exhumation.objects.filter(
        defunt=defunt,
        statut__in=['en_attente', 'validee']
    ).first()
    
    if demande_existante:
        return {
            "error": "Une demande d'exhumation existe déjà pour ce défunt",
            "statut": demande_existante.statut,
            "id": demande_existante.id
        }, 409
    
    e = Exhumation.objects.create(
        caveau=defunt.caveau,
        defunt=defunt,
        demandeur=request.user,
        motif=data.motif,
        document_legal=data.document_legal,
        date_souhaitee=data.date_souhaitee,
        statut='en_attente'
    )
    
    # Notification aux admins
    notifier_admins_nouvelle_exhumation(e)
    
    return {"id": e.id, "ok": True}

@api.post("/exhumations/{eid}/valider", auth=token_auth)
def valider_exhumation(request, eid: int):
    """Valide une demande d'exhumation (réservé admin/secrétariat)"""
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus:
        return refus
    
    exhumation = Exhumation.objects.filter(id=eid).select_related('defunt__caveau__cimetiere').first()
    if not exhumation:
        return {"error": "Demande introuvable"}, 404
    
    if exhumation.defunt.caveau.cimetiere != cimetiere_de(request):
        return {"error": "Accès non autorisé"}, 403
    
    if exhumation.statut != 'en_attente':
        return {"error": f"Cette demande est déjà {exhumation.statut}"}, 400
    
    exhumation.statut = 'validee'
    exhumation.date_validation = timezone.now()
    exhumation.validateur = request.user
    exhumation.save()
    
    # Notification au demandeur
    envoyer_notification_validation_exhumation(exhumation)
    
    return {"id": exhumation.id, "statut": "validee", "ok": True}

@api.post("/exhumations/{eid}/realiser", auth=token_auth)
def realiser_exhumation(request, eid: int):
    """Marque l'exhumation comme réalisée (libère le caveau)"""
    refus = refuser_si_role_absent(request, ['admin', 'agent'])
    if refus:
        return refus
    
    exhumation = Exhumation.objects.filter(id=eid).select_related('defunt__caveau__cimetiere').first()
    if not exhumation:
        return {"error": "Demande introuvable"}, 404
    
    if exhumation.statut != 'validee':
        return {"error": "L'exhumation doit être validée avant d'être réalisée"}, 400
    
    exhumation.statut = 'realisee'
    exhumation.date_realisation = timezone.now()
    exhumation.save()
    
    # Libérer le caveau
    exhumation.defunt.caveau.statut = 'disponible'
    exhumation.defunt.caveau.save()
    
    return {"id": exhumation.id, "statut": "realisee", "ok": True}

# ═══════════════════════════════════════════════════
# PAIEMENTS
# ═══════════════════════════════════════════════════
@api.post("/paiement/simuler", auth=token_auth)
def simuler_paiement(request, data: PaiementSimuleSchema):
    """Simule un paiement, met à jour le statut et envoie le reçu par email"""
    reservation = Reservation.objects.filter(id=data.reservation_id).first()
    if not reservation:
        return {"error": "Réservation introuvable"}, 404
    
    montant_reel = float(reservation.montant_total)
    transaction_id = f"TXN-{random.randint(100000, 999999)}"
    
    # Mise à jour du statut
    reservation.statut = 'payee'
    reservation.save()
    
    # Récupérer l'email du client (depuis la réservation ou l'utilisateur connecté)
    email_client = getattr(reservation, 'client_email', None) or \
                   (reservation.client.email if hasattr(reservation, 'client') and reservation.client else "client@exemple.com")
    
    # Tentative d'envoi d'email (fail_silently=True évite le crash si SMTP n'est pas configuré)
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f"Reçu de paiement - Réservation #{reservation.id}",
            message=f"Bonjour,\n\nNous vous confirmons la réception de votre paiement de {montant_reel} FCFA.\nRéférence de la transaction : {transaction_id}\n\nMerci de votre confiance.\nL'équipe NECROPOLIS",
            from_email="noreply@necropolis.cg",  # À changer par ton vrai email d'expédition
            recipient_list=[email_client],
            fail_silently=True, 
        )
        print(f"✅ Email de reçu envoyé (ou simulé) à : {email_client}")
    except Exception as e:
        print(f"⚠️ Erreur d'envoi d'email (SMTP non configuré) : {e}")

    return {
        "message": f"Paiement effectué avec succès via {data.methode}",
        "montant": montant_reel,
        "transaction_id": transaction_id,
        "email_client": email_client,
        "statut": "success"
    }

# ═══════════════════════════════════════════════════
# CARTE
# ═══════════════════════════════════════════════════
@api.get("/carte", auth=token_auth)
def carte_cimetiere(request):
    """Génère une carte avec les caveaux POSITIONNÉS DANS le cimetière"""
    import folium
    from django.db.models import Avg
    
    # Récupérer le token depuis les paramètres GET
    token = request.GET.get('token', '')
    
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return {"error": "Aucun cimetiere actif"}, 404
    
    # Coordonnées du centre du cimetière
    lat_centre = cimetiere.latitude or -4.7692
    lng_centre = cimetiere.longitude or 11.8634
    
    # Limites du cimetière (ou valeurs par défaut)
    limite_nord = getattr(cimetiere, 'limite_nord', None) or lat_centre + 0.005
    limite_sud = getattr(cimetiere, 'limite_sud', None) or lat_centre - 0.005
    limite_est = getattr(cimetiere, 'limite_est', None) or lng_centre + 0.005
    limite_ouest = getattr(cimetiere, 'limite_ouest', None) or lng_centre - 0.005
    
    # Créer la carte
    carte = folium.Map(
        location=[lat_centre, lng_centre],
        zoom_start=18,
        tiles='OpenStreetMap',
        prefer_canvas=True
    )
    
    # Délimiter le cimetière avec un fond SOBRE
    folium.Rectangle(
        bounds=[[limite_sud, limite_ouest], [limite_nord, limite_est]],
        color="#8B7355",
        weight=2,
        fill=True,
        fill_color="#D2B48C",
        fill_opacity=0.35,
        popup=f"Cimetière: {cimetiere.nom}"
    ).add_to(carte)
    
    # Récupérer tous les caveaux
    caveaux = Caveau.objects.filter(cimetiere=cimetiere).order_by('section', 'bloc', 'numero')
    
    # Calculer la grille
    sections = sorted(list(set(c.section for c in caveaux if c.section)))
    blocs = sorted(list(set(c.bloc for c in caveaux if c.bloc)))
    nb_sections = len(sections) if sections else 1
    nb_blocs = len(blocs) if blocs else 1
    
    # Espacement entre chaque section et bloc
    pas_lat = (limite_nord - limite_sud) / (nb_sections + 1)
    pas_lng = (limite_est - limite_ouest) / (nb_blocs + 1)
    
    couleurs = {'disponible': 'green', 'reserve': 'orange', 'occupe': 'red', 'non_exploitable': 'gray'}
    markers = folium.FeatureGroup(name="Caveaux")
    
    for c in caveaux:
        # Si le caveau a déjà des coordonnées GPS, les utiliser
        if hasattr(c, 'localisation') and c.localisation:
            lat, lng = c.localisation.y, c.localisation.x
        else:
            # SINON: Calculer la position dans la grille
            try:
                idx_section = sections.index(c.section) if c.section in sections else 0
                idx_bloc = blocs.index(c.bloc) if c.bloc in blocs else 0
                # Positionner DANS le cimetière
                lat = limite_nord - (pas_lat * (idx_section + 1))
                lng = limite_ouest + (pas_lng * (idx_bloc + 1))
                # SAUVEGARDER ces coordonnées dans le caveau pour la prochaine fois
                from django.contrib.gis.geos import Point
                c.localisation = Point(lng, lat)
                c.save(update_fields=['localisation'])
            except Exception as e:
                print(f"Erreur positionnement caveau {c.id}: {e}")
                lat, lng = lat_centre, lng_centre
        
        couleur = couleurs.get(c.statut, 'blue')
        prix = getattr(c, 'prix', 750000)
        prix_fmt = f"{prix:,.0f}".replace(",", " ")
        
        popup_html = f"""
        <div style='width: 250px; padding: 12px; font-family: Arial, sans-serif;'>
            <h4 style='margin: 0 0 10px 0; color: #333; border-bottom: 2px solid #c9a84c; padding-bottom: 8px;'>
                Caveau N° {c.numero}
            </h4>
            <p style='margin: 5px 0; color: #666; font-size: 13px;'>
                📍 Section {c.section} - Bloc {c.bloc}
            </p>
            <p style='margin: 5px 0;'>
                Statut: <strong style='color: {couleur}; font-size: 14px;'>{c.statut.upper()}</strong>
            </p>
            <p style='margin: 8px 0; color: #c9a84c; font-weight: bold; font-size: 16px;'>
                 Prix: {prix_fmt} FCFA
            </p>
        """
        
        if c.statut == 'disponible':
            popup_html += f"""
            <button onclick="selectionnerCaveau({c.id}, '{c.numero}', {prix})" 
                    style='width: 100%; margin-top: 12px; padding: 12px; background: #28a745; 
                           color: white; border: none; border-radius: 6px; cursor: pointer; 
                           font-weight: bold; font-size: 14px;'>
                ✅ OUI, JE VEUX RÉSERVER
            </button>
            <div id='message_{c.id}' style='display: none; margin-top: 10px; padding: 10px; 
                    background: #d4edda; color: #155724; border-radius: 5px; text-align: center; 
                    font-weight: bold;'>
                ✓ Sélectionné !
            </div>
            """
        else:
            popup_html += f"""
            <p style='margin: 10px 0 0 0; color: #999; font-style: italic; font-size: 12px;'>
                Ce caveau n'est pas disponible
            </p>
            """
        
        popup_html += "</div>"
        
        folium.CircleMarker(
            location=[lat, lng],
            radius=10,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{c.numero} - {prix_fmt} FCFA"
        ).add_to(markers)
    
    markers.add_to(carte)
    folium.LayerControl().add_to(carte)
    
    # Légende
    legend_html = """
    <div style='position: fixed; bottom: 20px; left: 20px; z-index: 1000; 
                background: rgba(0,0,0,0.85); padding: 15px; border-radius: 10px; 
                color: white; font-family: Arial, sans-serif; border: 1px solid #c9a84c;'>
        <h4 style='margin: 0 0 10px 0; color: #c9a84c;'>Légende</h4>
        <p style='margin: 5px 0;'><span style='display: inline-block; width: 12px; height: 12px; 
            background: green; border-radius: 50%; margin-right: 8px;'></span>Disponible</p>
        <p style='margin: 5px 0;'><span style='display: inline-block; width: 12px; height: 12px; 
            background: orange; border-radius: 50%; margin-right: 8px;'></span>Réservé</p>
        <p style='margin: 5px 0;'><span style='display: inline-block; width: 12px; height: 12px; 
            background: red; border-radius: 50%; margin-right: 8px;'></span>Occupé</p>
    </div>
    """
    carte.get_root().html.add_child(folium.Element(legend_html))
    
    # Script JavaScript AVEC LE TOKEN INJECTÉ
    script_html = f"""
    <script>
    const NECROPOLIS_TOKEN = '{token}';
    
    function selectionnerCaveau(id, numero, prix) {{
        if (!NECROPOLIS_TOKEN) {{
            alert('❌ Session expirée. Veuillez vous reconnecter.');
            return;
        }}
        
        var msgDiv = document.getElementById('message_' + id);
        if (msgDiv) {{
            msgDiv.style.display = 'block';
            msgDiv.innerHTML = '⏳ Envoi en cours...';
            msgDiv.style.background = '#fff3cd';
            msgDiv.style.color = '#856404';
        }}
        
        fetch('http://127.0.0.1:8000/api/selectionner-caveau/' + id + '/', {{
            method: 'POST',
            headers: {{ 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + NECROPOLIS_TOKEN
            }}
        }})
        .then(response => {{
            if (response.status === 401) {{
                alert('❌ Session expirée. Veuillez vous reconnecter.');
                return null;
            }}
            return response.json();
        }})
        .then(data => {{
            if (!data) return;
            if(data.success) {{
                if (msgDiv) {{
                    msgDiv.innerHTML = '✅ Caveau sélectionné !<br>Prix: ' + prix.toLocaleString() + ' FCFA<br><small>Retournez dans l\\'application</small>';
                    msgDiv.style.background = '#d4edda';
                    msgDiv.style.color = '#155724';
                }}
                alert('✅ Caveau N°' + numero + ' sélectionné avec succès !\\n\\nPrix: ' + prix.toLocaleString() + ' FCFA\\n\\n' +
                      'Retournez dans l\\'application NECROPOLIS > Réservations\\n' +
                      'Le caveau sera automatiquement pré-sélectionné.');
            }} else {{
                if (msgDiv) {{
                    msgDiv.innerHTML = '❌ Erreur: ' + (data.error || 'Inconnue');
                    msgDiv.style.background = '#f8d7da';
                    msgDiv.style.color = '#721c24';
                }}
                alert('❌ Erreur: ' + (data.error || 'Caveau non disponible'));
            }}
        }})
        .catch(error => {{
            console.error("Erreur:", error);
            if (msgDiv) {{
                msgDiv.innerHTML = '❌ Erreur de connexion';
                msgDiv.style.background = '#f8d7da';
                msgDiv.style.color = '#721c24';
            }}
            alert(' Erreur de connexion au serveur.\\n\\n' +
                  'Vérifiez que :\\n' +
                  '1. Le serveur Django est démarré (python manage.py runserver)\\n' +
                  '2. Vous êtes connecté à l\\'application NECROPOLIS');
        }});
    }}
    </script>
    """
    carte.get_root().html.add_child(folium.Element(script_html))
    
    # Sauvegarder
    import tempfile, os
    chemin = os.path.join(tempfile.gettempdir(), "necropolis_carte.html")
    carte.save(chemin)
    with open(chemin, 'r', encoding='utf-8') as f:
        html_content = f.read()
    from django.http import HttpResponse
    return HttpResponse(html_content, content_type='text/html')

# ── CIMETIÈRES PAR VILLE (accès public) ─────────────────
@api.get("/cimetières/par-ville", auth=token_auth)
def cimetières_par_ville(request):
    """Liste tous les cimetières groupés par ville avec stats"""
    from django.db.models import Count, Q
    
    villes = Cimetiere.objects.all().values('ville', 'pays').annotate(
        total_cimetières=Count('id'),
        total_caveaux=Count('caveaux'),
        caveaux_disponibles=Count('caveaux', filter=Q(caveaux__statut='disponible'))
    ).order_by('ville')
    
    return list(villes)

@api.get("/caveaux/recherche", auth=token_auth)
def rechercher_caveaux(request, ville: str = None):
    """Recherche des caveaux disponibles par ville"""
    qs = Caveau.objects.filter(statut='disponible')
    
    if ville:
        qs = qs.filter(cimetiere__ville__icontains=ville)
    
    results = []
    for c in qs.select_related('cimetiere')[:100]:
        results.append({
            "id": c.id,
            "numero": c.numero,
            "section": c.section,
            "bloc": c.bloc,
            "cimetiere": c.cimetiere.nom,
            "ville": c.cimetiere.ville,
            "pays": c.cimetiere.pays,
            "latitude": c.cimetiere.latitude,
            "longitude": c.cimetiere.longitude,
        })
    
    return results

#@api.get("/carte/publique", auth=token_auth)
def carte_publique(request):
    """Carte montrant TOUS les cimetières (pour clients/public) - Zoom niveau quartier"""
    # Centre par défaut sur le Congo avec zoom plus rapproché
    centre = [-4.7761, 11.8635]
    
    carte = folium.Map(location=centre, zoom_start=13)  # Zoom 13 au lieu de 7 pour voir les quartiers
    
    cimetières = Cimetiere.objects.all()
    couleurs_cimetière = ['#FF0000', '#00FF00', '#0000FF', '#FFA500', '#800080', '#008080', '#FFC0CB', '#A52A2A']
    
    for idx, cimetiere in enumerate(cimetières):
        couleur = couleurs_cimetière[idx % len(couleurs_cimetière)]
        
        if cimetiere.latitude and cimetiere.longitude:
            folium.CircleMarker(
                location=[cimetiere.latitude, cimetiere.longitude],
                radius=20,  # Rayon plus grand pour mieux voir
                color=couleur, fill=True, fill_color=couleur, fill_opacity=0.7,
                popup=folium.Popup(f"<b>{cimetiere.nom}</b><br>Ville: {cimetiere.ville}<br>Caveaux: {cimetiere.caveaux.count()}", max_width=250)
            ).add_to(carte)
        
        couleurs_statut = {'disponible': 'green', 'reserve': 'orange', 'occupe': 'red', 'non_exploitable': 'gray'}
        for caveau in cimetiere.caveaux.all():
            if caveau.localisation:
                lat = caveau.localisation.y
                lng = caveau.localisation.x
            else:
                continue
            
            couleur_statut = couleurs_statut.get(caveau.statut, 'blue')
            folium.CircleMarker(
                location=[lat, lng], radius=10, color=couleur_statut, fill=True, fill_color=couleur_statut, fill_opacity=0.9,
                popup=folium.Popup(f"<b>Caveau N° {caveau.numero}</b><br>Cimetière: {cimetiere.nom}<br>Statut : {caveau.statut}", max_width=200)
            ).add_to(carte)
    
    legende = """
    <div style="position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #1a1a1a; color: #c9a84c; padding: 12px 20px; border-radius: 8px; font-family: monospace; font-size: 13px; border: 1px solid #c9a84c; z-index: 9999; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
        🗺️ <b>VUE MULTI-CIMETIÈRES - Niveau Quartier</b><br>🟢 Disponible &nbsp; 🟠 Réservé &nbsp; 🔴 Occupé &nbsp;  Non exploitable
    </div>
    """
    carte.get_root().html.add_child(folium.Element(legende))
    return DjangoResponse(carte._repr_html_(), content_type='text/html')

# ═══════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════
@api.get("/export/caveaux/csv", auth=token_auth)
def export_caveaux_csv(request):
    import csv
    cimetiere = cimetiere_de(request)
    response = DjangoResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="caveaux.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Numero', 'Section', 'Bloc', 'Statut'])
    qs = Caveau.objects.filter(cimetiere=cimetiere) if cimetiere else Caveau.objects.none()
    for c in qs:
        writer.writerow([c.id, c.numero, c.section, c.bloc, c.statut])
    return response

@api.get("/export/caveaux/excel", auth=token_auth)
def export_caveaux_excel(request):
    from openpyxl import Workbook
    from io import BytesIO
    cimetiere = cimetiere_de(request)
    wb = Workbook()
    ws = wb.active
    ws.title = "Caveaux"
    ws.append(['ID', 'Numero', 'Section', 'Bloc', 'Statut'])
    qs = Caveau.objects.filter(cimetiere=cimetiere) if cimetiere else Caveau.objects.none()
    for c in qs:
        ws.append([c.id, c.numero, c.section, c.bloc, c.statut])
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = DjangoResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="caveaux.xlsx"'
    return response

@api.get("/export/reservations/csv", auth=token_auth)
def export_reservations_csv(request):
    import csv
    cimetiere = cimetiere_de(request)
    response = DjangoResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reservations.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Client', 'Caveau', 'Statut', 'Date'])
    qs = Reservation.objects.filter(caveau__cimetiere=cimetiere) if cimetiere else Reservation.objects.none()
    for r in qs.select_related('caveau', 'client'):
        writer.writerow([r.id, r.client.username, r.caveau.numero, r.statut, r.date_reservation])
    return response
    

@api.get("/exhumations", auth=token_auth)
def liste_exhumations(request):
    """Renvoie la liste des demandes d'exhumation du cimetière"""
    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return []
    
    # On récupère les exhumations liées aux défunts de ce cimetière
    qs = Exhumation.objects.filter(defunt__caveau__cimetiere=cimetiere).select_related('defunt')
    
    data = []
    for e in qs:
        data.append({
            "id": e.id,
            "defunt_id": e.defunt.id if e.defunt else None,
            "defunt_nom": f"{e.defunt.prenom} {e.defunt.nom}".strip() if e.defunt else "Inconnu",
            "motif": e.motif,
            "statut": e.statut,
        })
    return data  

@api.get("/cimetiere/actuel", auth=token_auth)
def cimetiere_actuel(request):
    """Renvoie les infos du cimetière de l'utilisateur connecté"""
    cimetiere = cimetiere_de(request)
    
    if not cimetiere:
        # On retourne directement le dict, Django Ninja gère le reste
        return {"error": "Aucun cimetière associé à ce compte"}
    
    return {
        "id": cimetiere.id,
        "nom": cimetiere.nom,
        "ville": cimetiere.ville,
        "quartier": cimetiere.quartier,
        "pays": cimetiere.pays,
        "latitude": cimetiere.latitude,
        "longitude": cimetiere.longitude,
        "superficie_totale": cimetiere.superficie_totale,
        "nombre_places_estime": cimetiere.nombre_places_estime,
    }

@api.delete("/reservations/{rid}", auth=token_auth)
def supprimer_reservation(request, rid: int):
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus:
        return refus
    
    cimetiere = cimetiere_de(request)
    reservation = Reservation.objects.filter(id=rid, caveau__cimetiere=cimetiere).select_related('caveau').first()
    
    if not reservation:
        return api.create_response(request, {"error": "Reservation introuvable"}, status=404)
    
    # Libérer le caveau
    if reservation.caveau:
        reservation.caveau.statut = 'disponible'
        reservation.caveau.save()
    
    # Supprimer le défunt associé
    if reservation.defunt:
        reservation.defunt.delete()
    
    # Supprimer la réservation
    reservation_id = reservation.id
    reservation.delete()
    
    return {"ok": True, "message": f"Reservation #{reservation_id} supprimee"}


# 1. Quand l'app demande "/equipe", on utilise la fonction "lister_membres"
@api.get("/equipe", auth=token_auth)
def get_equipe_alias(request):
    return lister_membres(request)

# 2. Quand l'app demande "/exports/..." (avec un 's'), on utilise les fonctions "export/..." (sans 's')
@api.get("/exports/caveaux/excel", auth=token_auth)
def export_caveaux_excel_alias(request):
    return export_caveaux_excel(request)

@api.get("/exports/caveaux/csv", auth=token_auth)
def export_caveaux_csv_alias(request):
    return export_caveaux_csv(request)

# Alias pour AJOUTER un membre de l'équipe (POST)
@api.post("/equipe", auth=token_auth)
def create_equipe_alias(request, data: CreerMembreSchema):
    return creer_membre(request, data)   

# ═══════════════════════════════════════════════════
# CORRECTIONS FINALES : ALIAS ET PAIEMENT
# ═══════════════════════════════════════════════════

# 1. Alias pour AJOUTER un membre (POST /equipe)
@api.post("/equipe", auth=token_auth)
def create_equipe_post(request, body: CreerMembreSchema):
    return creer_membre(request, body)

# 2. Alias pour les exports manquants
@api.get("/exports/defunts/excel", auth=token_auth)
def export_defunts_excel_alias(request):
    # On crée une fonction rapide pour exporter les défunts
    from openpyxl import Workbook
    from io import BytesIO
    from django.http import HttpResponse as DjangoResponse
    
    cimetiere = cimetiere_de(request)
    wb = Workbook()
    ws = wb.active
    ws.title = "Défunts"
    ws.append(['Nom', 'Prénom', 'Date de décès', 'Caveau'])
    
    if cimetiere:
        defunts = Defunt.objects.filter(caveau__cimetiere=cimetiere)
        for d in defunts:
            ws.append([d.nom, d.prenom, d.date_deces, d.caveau.numero if d.caveau else ''])
            
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = DjangoResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="defunts.xlsx"'
    return response

@api.get("/exports/concessions/pdf", auth=token_auth)
def export_concessions_pdf(request):
    """Génère un PDF récapitulatif de TOUTES les concessions du cimetière"""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from django.http import HttpResponse as DjangoResponse
    from datetime import datetime

    cimetiere = cimetiere_de(request)
    if not cimetiere:
        return api.create_response(request, {"error": "Aucun cimetière associé"}, status=403)

    # Récupérer toutes les concessions du cimetière
    concessions = Concession.objects.filter(caveau__cimetiere=cimetiere).select_related('caveau', 'client')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # ── EN-TÊTE ──
    elements.append(Paragraph("NECROPOLIS - RÉPUBLIQUE DU CONGO", styles['Title']))
    elements.append(Paragraph("REGISTRE OFFICIEL DES CONCESSIONS", styles['Heading2']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Cimetière :</b> {cimetiere.nom}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date d'export :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # ── TABLEAU DES CONCESSIONS ──
    data_table = [['ID', 'Caveau', 'Type', 'Bénéficiaire', 'Début', 'Fin', 'Montant']]
    for c in concessions:
        data_table.append([
            str(c.id),
            c.caveau.numero,
            c.type_concession.capitalize(),
            c.beneficiaire or "N/A",
            c.date_debut.strftime('%d/%m/%Y') if c.date_debut else 'N/A',
            c.date_fin.strftime('%d/%m/%Y') if c.date_fin else 'Perpétuelle',
            f"{c.montant} FCFA"
        ])

    # Ajustement des largeurs de colonnes pour que ça tienne sur une page A4
    table = Table(data_table, colWidths=[30, 50, 60, 100, 60, 60, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c9a84c')), # Or NECROPOLIS
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)

    # ── PIED DE PAGE ──
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        f"Ce document certifie l'état des concessions du cimetière {cimetiere.nom} à la date mentionnée. "
        f"Total de {concessions.count()} concession(s) enregistrée(s).",
        styles['Italic']
    ))

    doc.build(elements)
    buffer.seek(0)
    
    response = DjangoResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="concessions_{cimetiere.nom}.pdf"'
    return response    

@api.get("/exports/reservations/csv", auth=token_auth)
def export_reservations_csv_alias(request):
    return export_reservations_csv(request)

# 3. Correction du Paiement (pour éviter le 422)
class PaiementSchema(Schema):
    reservation_id: int
    methode: str
    numero_telephone: str = ""
    montant: float = 0

class PaiementPartielSchema(Schema):
    reservation_id: int
    methode: str
    numero_telephone: str = ""
    montant: float  # Le montant exact que le client choisit de payer maintenant

@api.post("/paiement/simuler", auth=token_auth)
def simuler_paiement_partiel(request, data: PaiementPartielSchema):
    """Gère les paiements partiels ou totaux et crée l'historique (Transaction)"""
    reservation = Reservation.objects.filter(id=data.reservation_id).first()
    if not reservation:
        return {"error": "Réservation introuvable"}, 404

    # 1. Créer la transaction (Historique)
    transaction_id = f"TXN-{random.randint(100000, 999999)}"
    Transaction.objects.create(
        reservation=reservation,
        montant=data.montant,
        methode=data.methode,
        numero_telephone=data.numero_telephone,
        reference_transaction=transaction_id
    )

    # 2. Mettre à jour le montant payé sur la réservation
    reservation.montant_paye = (reservation.montant_paye or 0) + data.montant
    reservation.save()

    # 3. Vérifier si la réservation est entièrement payée
    if reservation.montant_paye >= reservation.montant_total:
        reservation.statut = 'payee'
        reservation.save()
        message_statut = "La réservation est maintenant entièrement payée !"
    else:
        reste_a_payer = reservation.montant_total - reservation.montant_paye
        message_statut = f"Paiement partiel enregistré. Reste à payer : {reste_a_payer} FCFA."

    # 4. Email de reçu (simulé)
    email_client = getattr(reservation, 'client_email', None) or (reservation.client.email if reservation.client else "client@exemple.com")
    try:
        send_mail(
            subject=f"Reçu de paiement - Réservation #{reservation.id}",
            message=f"Bonjour,\n\nNous confirmons la réception de {data.montant} FCFA.\n"
                    f"Référence : {transaction_id}\n"
                    f"Total payé à ce jour : {reservation.montant_paye} FCFA sur {reservation.montant_total} FCFA.\n\n"
                    f"{message_statut}\n\nL'équipe NECROPOLIS",
            from_email="noreply@necropolis.cg",
            recipient_list=[email_client],
            fail_silently=True,
        )
    except Exception as e:
        print(f"⚠️ Erreur email: {e}")

    return {
        "message": f"Paiement de {data.montant} FCFA effectué via {data.methode}. {message_statut}",
        "transaction_id": transaction_id,
        "montant_paye_total": float(reservation.montant_paye),
        "reste_a_payer": float(reservation.montant_total - reservation.montant_paye),
        "statut": "success"
    }

# ═══════════════════════════════════════════════════
# NOUVEAU : HISTORIQUE DES TRANSACTIONS (CDC 2.6)
# ═══════════════════════════════════════════════════
@api.get("/paiement/historique/{reservation_id}", auth=token_auth)
def historique_paiement(request, reservation_id: int):
    """Renvoie la liste de tous les paiements effectués pour une réservation"""
    transactions = Transaction.objects.filter(reservation_id=reservation_id).order_by('-date_transaction')
    return [
        {
            "id": t.id,
            "montant": float(t.montant),
            "methode": t.methode,
            "reference": t.reference_transaction,
            "date": t.date_transaction.strftime("%d/%m/%Y %H:%M"),
            "telephone": t.numero_telephone
        }
        for t in transactions
    ]

# ═══════════════════════════════════════════════════
# NOUVEAU : ALERTES RETARDS DE PAIEMENT (CDC 6)
# ═══════════════════════════════════════════════════
@api.get("/dashboard/alertes-paiements", auth=token_auth)
def alertes_retards_paiement(request):
    """Renvoie les réservations en attente de paiement depuis plus de 48h"""
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus: return refus
    
    cimetiere = cimetiere_de(request)
    if not cimetiere: return []

    # Réservations validées ou en attente, mais pas totalement payées, créées il y a plus de 2 jours
    seuil = timezone.now() - timedelta(days=2)
    from django.db.models import F
    retards = Reservation.objects.filter(
        caveau__cimetiere=cimetiere,
        statut__in=['en_attente', 'validee'],
        date_reservation__lt=seuil,
        montant_paye__lt=F('montant_total')
    ).select_related('caveau')
    
    return [
        {
            "id": r.id,
            "caveau_numero": r.caveau.numero,
            "client": r.client_nom or r.client.username,
            "montant_du": float(r.montant_total - r.montant_paye),
            "date_reservation": r.date_reservation.strftime("%d/%m/%Y")
        }
        for r in retards
    ]

@api.get("/concessions/{cid}/contrat", auth=token_auth)
def contrat_concession(request, cid: int):
    """Génère le certificat officiel de concession"""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from django.http import HttpResponse as DjangoResponse
    
    cimetiere = cimetiere_de(request)
    concession = Concession.objects.filter(id=cid, caveau__cimetiere=cimetiere).select_related('caveau', 'client').first()
    if not concession:
        return {"error": "Concession introuvable"}

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("NECROPOLIS - RÉPUBLIQUE DU CONGO", styles['Title']))
    elements.append(Paragraph("CERTIFICAT OFFICIEL DE CONCESSION", styles['Heading2']))
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph(f"<b>N° de Contrat :</b> CONC-{concession.id}-2026", styles['Normal']))
    elements.append(Paragraph(f"<b>Date d'émission :</b> {concession.date_debut.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("TITULAIRE DU CONTRAT", styles['Heading3']))
    elements.append(Paragraph(f"Nom : {concession.client.get_full_name() or concession.client.username}", styles['Normal']))
    elements.append(Paragraph(f"Email : {concession.client.email}", styles['Normal']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("DÉTAILS DE LA CONCESSION", styles['Heading3']))
    data_table = [
        ['Caveau N°', concession.caveau.numero],
        ['Section / Bloc', f"{concession.caveau.section} / {concession.caveau.bloc}"],
        ['Type', concession.type_concession.capitalize()],
        ['Date de début', concession.date_debut.strftime('%d/%m/%Y')],
        ['Date de fin', concession.date_fin.strftime('%d/%m/%Y') if concession.date_fin else 'Perpétuelle'],
        ['Montant payé', f"{concession.montant} FCFA"],
    ]
    table = Table(data_table, colWidths=[150, 250])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c9a84c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Ce document certifie que le titulaire dispose des droits funéraires sur le caveau désigné pour la durée stipulée.", styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    response = DjangoResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contrat_concession_{cid}.pdf"'
    return response  

# ═══════════════════════════════════════════════════
# FONCTIONS DE NOTIFICATION (SMS + EMAIL)
# ═══════════════════════════════════════════════════

def envoyer_notification_concession(concession, client):
    """Envoie SMS + Email lors de la création d'une concession"""
    # 1. SMS (simulé - à remplacer par un vrai provider comme Twilio)
    telephone = getattr(client.profil, 'telephone', None) if hasattr(client, 'profil') else None
    if telephone:
        message_sms = f"NECROPOLIS: Concession {concession.type_concession} créée. Caveau N°{concession.caveau.numero}. Fin: {concession.date_fin or 'Perpétuelle'}."
        print(f"📱 SMS envoyé à {telephone}: {message_sms}")
    
    # 2. Email
    try:
        from django.core.mail import send_mail
        send_mail(
            subject="Confirmation de concession - NECROPOLIS",
            message=f"Bonjour,\n\nVotre concession {concession.type_concession} a été créée avec succès.\nCaveau N°: {concession.caveau.numero}\nDate de fin: {concession.date_fin or 'Perpétuelle'}\nMontant: {concession.montant} FCFA\n\nMerci de votre confiance.\nL'équipe NECROPOLIS",
            from_email="noreply@necropolis.cg",
            recipient_list=[client.email],
            fail_silently=True,  # Ne plante pas si SMTP non configuré
        )
        print(f"📧 Email envoyé à {client.email}")
    except Exception as e:
        print(f"⚠️ Erreur email: {e}")


def envoyer_notification_renouvellement(concession, nouvelle_date, montant):
    """Envoie SMS + Email lors du renouvellement d'une concession"""
    client = concession.client
    
    # 1. SMS
    telephone = getattr(client.profil, 'telephone', None) if hasattr(client, 'profil') else None
    if telephone:
        message_sms = f"NECROPOLIS: Concession renouvelée jusqu'au {nouvelle_date}. Montant: {montant} FCFA."
        print(f"📱 SMS envoyé à {telephone}: {message_sms}")
    
    # 2. Email
    try:
        from django.core.mail import send_mail
        send_mail(
            subject="Renouvellement de concession - NECROPOLIS",
            message=f"Bonjour,\n\nVotre concession du caveau N°{concession.caveau.numero} a été renouvelée.\nNouvelle date de fin: {nouvelle_date}\nMontant payé: {montant} FCFA\n\nL'équipe NECROPOLIS",
            from_email="noreply@necropolis.cg",
            recipient_list=[client.email],
            fail_silently=True,
        )
        print(f"📧 Email de renouvellement envoyé à {client.email}")
    except Exception as e:
        print(f"⚠️ Erreur email: {e}")


def notifier_admins_nouvelle_exhumation(exhumation):
    """Notifie les admins d'une nouvelle demande d'exhumation"""
    from django.contrib.auth.models import User
    admins = User.objects.filter(profil__role__in=['admin', 'secretariat'])
    
    message = f"NOUVELLE EXHUMATION: Demande #{exhumation.id} pour {exhumation.defunt.nom} {exhumation.defunt.prenom}. Motif: {exhumation.motif}."
    
    for admin in admins:
        telephone = getattr(admin.profil, 'telephone', None) if hasattr(admin, 'profil') else None
        if telephone:
            print(f"📱 SMS admin à {telephone}: {message}")
        
        try:
            from django.core.mail import send_mail
            send_mail(
                subject="Nouvelle demande d'exhumation",
                message=message,
                from_email="noreply@necropolis.cg",
                recipient_list=[admin.email],
                fail_silently=True,
            )
        except:
            pass


def envoyer_alerte_expiration_concessions():
    """À appeler périodiquement : alerte les concessions qui expirent bientôt"""
    from datetime import timedelta
    from django.utils import timezone
    from .models import Concession
    
    today = timezone.now().date()
    
    # Alertes à 6 mois, 1 mois, 1 semaine
    for delai_jours, label in [(180, "6 mois"), (30, "1 mois"), (7, "1 semaine")]:
        date_limite = today + timedelta(days=delai_jours)
        concessions = Concession.objects.filter(
            date_fin__lte=date_limite,
            date_fin__gte=today,
            type_concession__in=['temporaire', 'trentenaire']
        ).select_related('client', 'caveau')
        
        for c in concessions:
            message = f"ALERTE NECROPOLIS: Concession du caveau N°{c.caveau.numero} expire dans {label} (le {c.date_fin}). Contactez-nous pour renouvellement."
            
            telephone = getattr(c.client.profil, 'telephone', None) if hasattr(c.client, 'profil') else None
            if telephone:
                print(f"📱 SMS alerte à {telephone}: {message}")
            
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f"Alerte expiration - {label}",
                    message=message,
                    from_email="noreply@necropolis.cg",
                    recipient_list=[c.client.email],
                    fail_silently=True,
                )
            except:
                pass   

@api.get("/clients", auth=token_auth)
def liste_clients(request):
    """Liste tous les clients inscrits (réservé admin)"""
    refus = refuser_si_role_absent(request, ['admin'])
    if refus:
        return refus
    
    cimetiere = cimetiere_de(request)
    
    # Récupérer tous les utilisateurs avec le rôle 'client'
    from django.contrib.auth.models import User
    clients = User.objects.filter(profil__role='client').select_related('profil')
    
    data = []
    for client in clients:
        nb_reservations = Reservation.objects.filter(client=client).count()
        data.append({
            "id": client.id,
            "username": client.username,
            "nom": getattr(client.profil, 'nom', ''),
            "prenom": getattr(client.profil, 'prenom', ''),
            "email": client.email,
            "telephone": getattr(client.profil, 'telephone', 'N/A'),
            "date_inscription": client.date_joined.strftime("%d/%m/%Y"),
            "nb_reservations": nb_reservations,
        })
    return data  

import json
import os
import tempfile
from django.http import HttpResponse as DjangoResponse

FICHIER_SELECTION = os.path.join(tempfile.gettempdir(), "caveau_selectionne.json")

@api.post("/selectionner-caveau/{caveau_id}")  # ← PAS d'authentification
def selectionner_caveau(request, caveau_id: int):
    """Stocke le caveau sélectionné depuis la carte (accessible sans token)"""
    try:
        # Vérifier que le caveau existe et est disponible
        caveau = Caveau.objects.filter(id=caveau_id, statut='disponible').first()
        if not caveau:
            return {"success": False, "error": "Caveau non disponible"}
        
        # Lire le fichier existant
        data = {}
        if os.path.exists(FICHIER_SELECTION):
            with open(FICHIER_SELECTION, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        # Utiliser un ID de session unique au lieu de request.user.id
        session_id = request.session.session_key if request.session.session_key else "anonymous"
        
        # Stocker la sélection
        data[session_id] = {
            "caveau_id": caveau_id,
            "caveau_numero": caveau.numero,
            "section": caveau.section,
            "bloc": caveau.bloc,
        }
        
        with open(FICHIER_SELECTION, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        print(f"✅ CAVEAU SÉLECTIONNÉ : ID {caveau_id} (Session: {session_id})")
        return {"success": True, "caveau_id": caveau_id, "caveau_numero": caveau.numero}
    except Exception as e:
        print(f"❌ Erreur sélection carte: {e}")
        return {"success": False, "error": str(e)}

@api.get("/caveau-selectionne")  # ← PAS d'authentification
def get_caveau_selectionne(request):
    """Récupère et efface le caveau sélectionné (appelé par Flet)"""
    try:
        if not os.path.exists(FICHIER_SELECTION):
            return {"caveau_id": None}
        
        with open(FICHIER_SELECTION, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Utiliser le même session_id
        session_id = request.session.session_key if request.session.session_key else "anonymous"
        selection = data.get(session_id)
        
        if selection:
            # Effacer après lecture
            del data[session_id]
            with open(FICHIER_SELECTION, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            return {
                "caveau_id": selection["caveau_id"],
                "caveau_numero": selection.get("caveau_numero", "?"),
                "section": selection.get("section", ""),
                "bloc": selection.get("bloc", ""),
            }
        
        return {"caveau_id": None}
    except Exception as e:
        print(f"❌ Erreur lecture sélection: {e}")
        return {"caveau_id": None}

@api.post("/concessions/{cid}/resilier", auth=token_auth)
def resilier_concession(request, cid: int):
    """Résilie une concession (ex: pour non-paiement, abandon, ou réquisition) et libère le caveau"""
    refus = refuser_si_role_absent(request, ['admin', 'secretariat'])
    if refus: return refus
    
    cimetiere = cimetiere_de(request)
    concession = Concession.objects.filter(id=cid, caveau__cimetiere=cimetiere).select_related('caveau', 'client').first()
    
    if not concession:
        return api.create_response(request, {"error": "Concession introuvable dans votre cimetière"}, status=404)
    
    # Vérifier si elle n'est pas déjà expirée
    if concession.date_fin and concession.date_fin < timezone.now().date():
        return api.create_response(request, {"error": "Cette concession est déjà expirée, pas besoin de la résilier"}, status=400)

    # 1. Clôturer la concession (on met la date de fin à aujourd'hui)
    concession.date_fin = timezone.now().date()
    concession.save()

    # 2. Libérer le caveau associé
    caveau = concession.caveau
    caveau.statut = 'disponible'
    caveau.save()

    # 3. Journalisation (Audit Trail - Cahier des charges 4)
    AuditLog.objects.create(
        utilisateur=request.user,
        action="Résiliation de concession",
        objet_type="Concession",
        objet_id=concession.id,
        details=f"Concession du caveau {caveau.numero} résiliée par {request.user.username}"
    )

    # 4. Notification au client
    try:
        send_mail(
            'NECROPOLIS - Résiliation de votre concession',
            f'Bonjour,\n\nNous vous informons que la concession du caveau N°{caveau.numero} a été résiliée ce jour.\nLe caveau est désormais libéré.\n\nCordialement,\nNECROPOLIS',
            settings.DEFAULT_FROM_EMAIL,
            [concession.client.email],
            fail_silently=True,
        )
    except:
        pass

    return {"ok": True, "message": f"Concession résiliée. Le caveau N°{caveau.numero} est maintenant disponible."}

@api.get("/exhumations/{eid}/pv", auth=token_auth)
def pv_exhumation(request, eid: int):
    """Génère le Procès-Verbal (PV) officiel de l'exhumation"""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    cimetiere = cimetiere_de(request)
    exhumation = Exhumation.objects.filter(id=eid, defunt__caveau__cimetiere=cimetiere).select_related('defunt__caveau', 'demandeur', 'validateur').first()
    
    if not exhumation:
        return api.create_response(request, {"error": "Exhumation introuvable"}, status=404)
    
    if exhumation.statut != 'realisee':
        return api.create_response(request, {"error": "Le PV ne peut être généré que pour une exhumation réalisée"}, status=400)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # En-tête
    elements.append(Paragraph("RÉPUBLIQUE DU CONGO", styles['Title']))
    elements.append(Paragraph("MINISTÈRE DES AFFAIRES FUNÉRAIRES", styles['Heading3']))
    elements.append(Paragraph("NECROPOLIS - GESTION DE CIMETIÈRE", styles['Heading2']))
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph("PROCÈS-VERBAL D'EXHUMATION", styles['Heading1']))
    elements.append(Spacer(1, 20))

    # Infos générales
    elements.append(Paragraph(f"<b>N° de Dossier :</b> EXH-{exhumation.id}-2026", styles['Normal']))
    elements.append(Paragraph(f"<b>Date de réalisation :</b> {exhumation.date_realisation.strftime('%d/%m/%Y à %H:%M') if exhumation.date_realisation else 'N/A'}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Tableau des détails
    data_table = [
        ['Identité du défunt', f"{exhumation.defunt.prenom} {exhumation.defunt.nom}"],
        ['Date du décès initial', exhumation.defunt.date_deces.strftime('%d/%m/%Y')],
        ['Caveau d\'origine', f"N°{exhumation.defunt.caveau.numero} (Section {exhumation.defunt.caveau.section}, Bloc {exhumation.defunt.caveau.bloc})"],
        ['Cimetière', exhumation.defunt.caveau.cimetiere.nom],
        ['Motif de l\'exhumation', exhumation.motif],
        ['Demandeur', exhumation.demandeur.get_full_name() or exhumation.demandeur.username],
        ['Agent validateur', exhumation.validateur.get_full_name() or exhumation.validateur.username if exhumation.validateur else 'N/A'],
    ]
    
    table = Table(data_table, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Je soussigné(e), agent assermenté de la plateforme NECROPOLIS, certifie que l'exhumation mentionnée ci-dessus a été réalisée conformément à la réglementation en vigueur et aux autorisations légales fournies.", styles['Italic']))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Signature et Cachet :", styles['Normal']))
    elements.append(Paragraph("_________________________________", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    
    response = DjangoResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PV_Exhumation_{eid}.pdf"'
    return response

def envoyer_notification_validation_exhumation(exhumation):
    """Notifie le demandeur que son exhumation a été validée"""
    client = exhumation.demandeur
    message = f"NECROPOLIS: Votre demande d'exhumation #{exhumation.id} pour {exhumation.defunt.nom} a été VALIDÉE. Vous pouvez procéder à la réalisation."
    
    # 1. SMS (simulé)
    telephone = getattr(client.profil, 'telephone', None) if hasattr(client, 'profil') else None
    if telephone:
        print(f"📱 SMS envoyé à {telephone}: {message}")
    
    # 2. Email
    try:
        from django.core.mail import send_mail
        send_mail(
            subject="Validation de demande d'exhumation - NECROPOLIS",
            message=f"Bonjour,\n\n{message}\n\nCordialement,\nL'équipe NECROPOLIS",
            from_email="noreply@necropolis.cg",
            recipient_list=[client.email],
            fail_silently=True,
        )
        print(f"📧 Email de validation envoyé à {client.email}")
    except Exception as e:
        print(f"⚠️ Erreur email: {e}")    
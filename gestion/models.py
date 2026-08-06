import os
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models  # <-- Import standard compatible Render et SQLite


# ═══════════════════════════════════════════════════
# CONSTANTES GLOBALES (Définies AVANT les classes pour éviter les NameError)
# ═══════════════════════════════════════════════════

STATUT_CAVEAU_CHOICES = [
    ('disponible', 'Disponible'),
    ('reserve', 'Réservé'),
    ('occupe', 'Occupé'),
    ('non_exploitable', 'Non exploitable'),
]

TYPE_CAVEAU_CHOICES = [
    ('simple', 'Simple (1 place)'),
    ('double', 'Double (2 places)'),
    ('familial', 'Familial (4+ places)'),
]


# ═══════════════════════════════════════════════════
# MODÈLES
# ═══════════════════════════════════════════════════

class Cimetiere(models.Model):
    nom = models.CharField(max_length=150, unique=True)
    ville = models.CharField(max_length=100, blank=True, default="")
    pays = models.CharField(max_length=100, blank=True, default="République du Congo")
    quartier = models.CharField(max_length=100, blank=True, default="")
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    limite_nord = models.FloatField("Latitude limite Nord", null=True, blank=True)
    limite_sud = models.FloatField("Latitude limite Sud", null=True, blank=True)
    limite_est = models.FloatField("Longitude limite Est", null=True, blank=True)
    limite_ouest = models.FloatField("Longitude limite Ouest", null=True, blank=True)
    
    superficie_totale = models.FloatField("Superficie totale (m²)", default=0)
    tombeau_longueur = models.FloatField("Longueur standard d'un tombeau (m)", default=2.5)
    tombeau_largeur = models.FloatField("Largeur standard d'un tombeau (m)", default=1.2)
    nombre_places_estime = models.IntegerField(default=0)
    
    mot_de_passe_acces = models.CharField("Mot de passe d'accès (haché)", max_length=128)
    admin_createur = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cimetieres_crees'
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    def calculer_places(self, facteur_exploitable=0.7):
        surface_tombeau = (self.tombeau_longueur or 0) * (self.tombeau_largeur or 0)
        if not surface_tombeau or not self.superficie_totale:
            return 0
        surface_exploitable = self.superficie_totale * facteur_exploitable
        return int(surface_exploitable // surface_tombeau)

    def __str__(self):
        return self.nom


class Caveau(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    section = models.CharField(max_length=10)
    bloc = models.CharField(max_length=10)
    
    type_caveau = models.CharField(max_length=20, choices=TYPE_CAVEAU_CHOICES, default='simple')
    statut = models.CharField(max_length=20, choices=STATUT_CAVEAU_CHOICES, default='disponible')
    
    cimetiere = models.ForeignKey(Cimetiere, on_delete=models.CASCADE, related_name='caveaux')
    
    # MODIFICATION CLÉ : Champ texte standard compatible Render.
    # Il stockera les coordonnées au format "latitude,longitude" (ex: "-4.269, 15.266")
    # Ton interface pourra lire ce texte, le séparer et afficher la carte normalement.
    localisation = models.CharField(max_length=100, null=True, blank=True, verbose_name="Coordonnées (ex: -4.269, 15.266)")

    def __str__(self):
        return f"Caveau {self.numero} - {self.statut}"


class Defunt(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, default="")
    date_naissance = models.DateField(null=True, blank=True)
    date_deces = models.DateField()
    caveau = models.ForeignKey(Caveau, on_delete=models.SET_NULL, null=True, related_name='defunts')

    def __str__(self):
        return f"{self.nom} {self.prenom}"


class Reservation(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('validee', 'Validée'),
        ('annulee', 'Annulée'),
        ('payee', 'Payée'),
    ]
    
    caveau = models.ForeignKey(Caveau, on_delete=models.CASCADE, related_name='reservations')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    defunt = models.OneToOneField(Defunt, on_delete=models.CASCADE, null=True, blank=True)
    
    client_nom = models.CharField(max_length=100, blank=True, null=True)
    client_prenom = models.CharField(max_length=100, blank=True, null=True)
    client_email = models.EmailField(blank=True, null=True)
    client_telephone = models.CharField(max_length=20, blank=True, null=True)
    
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reservations_creees')
    valide_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reservations_validees')
    date_validation = models.DateTimeField(null=True, blank=True)
    
    type_caveau = models.CharField(max_length=20, default='simple')
    montant_total = models.DecimalField(max_digits=12, decimal_places=0, default=750000)
    montant_paye = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_reservation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_reservation']
    
    def __str__(self):
        return f"Réservation #{self.id} - {self.caveau.numero}"


class Concession(models.Model):
    TYPE_CHOICES = [
        ('temporaire', 'Temporaire'),
        ('perpetuelle', 'Perpétuelle'),
    ]

    caveau = models.ForeignKey(Caveau, on_delete=models.CASCADE, related_name='concessions')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='concessions')
    type_concession = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    renouvele = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    beneficiaire = models.CharField("Bénéficiaire", max_length=200, blank=True, default="")
    montant = models.DecimalField("Montant (FCFA)", max_digits=12, decimal_places=0, default=0)

    def __str__(self):
        return f"Concession {self.id} - {self.type_concession}"


class Exhumation(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('validee', 'Validée'),
        ('realisee', 'Réalisée'),
        ('refusee', 'Refusée'),
    ]
    caveau = models.ForeignKey(Caveau, on_delete=models.CASCADE)
    defunt = models.ForeignKey(Defunt, on_delete=models.CASCADE)
    demandeur = models.ForeignKey(User, on_delete=models.CASCADE)
    validateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='exhumations_validees')
    motif = models.TextField()
    document_legal = models.TextField(blank=True, default="")
    date_souhaitee = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_demande = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    date_realisation = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Exhumation {self.id} - {self.statut}"


class Profil(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('agent', 'Agent de terrain'),
        ('secretariat', 'Secretariat'),
        ('client', 'Client'),
    ]
    STATUT_CHOICES = [
        ('en_attente', 'En attente de validation'),
        ('valide', 'Valide'),
        ('refuse', 'Refusé'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cimetiere = models.ForeignKey(
        Cimetiere, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='membres'
    )
    nom = models.CharField(max_length=100, blank=True, default="")
    prenom = models.CharField(max_length=100, blank=True, default="")
    telephone = models.CharField(max_length=20, blank=True, default="")
    photo = models.CharField(max_length=255, blank=True, default="")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    code_mfa = models.CharField(max_length=6, blank=True, null=True)
    code_mfa_date = models.DateTimeField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    ville = models.CharField(max_length=100, blank=True, default="", verbose_name="Ville de résidence")

    def __str__(self):
        return f"{self.user.username} — {self.role} ({self.statut})"


class SessionToken(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_tokens')
    cle = models.CharField(max_length=64, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    derniere_utilisation = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Token {self.utilisateur.username}"


class AuditLog(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    objet_type = models.CharField(max_length=100)
    objet_id = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    def __str__(self):
        return f"{self.date} — {self.utilisateur} — {self.action}"


class CodeInvitation(models.Model):
    ROLE_CHOICES = [
        ('agent', 'Agent de terrain'),
        ('secretariat', 'Secretariat'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    cimetiere = models.ForeignKey(Cimetiere, on_delete=models.CASCADE, related_name='codes_invitation')
    role_autorise = models.CharField(max_length=20, choices=ROLE_CHOICES)
    utilise = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_utilisation = models.DateTimeField(null=True, blank=True)
    utilise_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='codes_utilises')

    def __str__(self):
        statut = "Utilisé" if self.utilise else "Disponible"
        return f"Code {self.code} ({self.cimetiere.nom}) - {statut}"


@receiver(post_save, sender=User)
def creer_profil_auto(sender, instance, created, **kwargs):
    if created:
        Profil.objects.create(user=instance)


class Transaction(models.Model):
    """Historique de chaque paiement (pour les paiements partiels)"""
    METHODE_CHOICES = [
        ('airtel_money', 'Airtel Money'),
        ('mtn_money', 'MTN Money'),
        ('mpesa', 'M-Pesa'),
        ('especes', 'Espèces'),
        ('virement', 'Virement bancaire'),
    ]
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='transactions')
    montant = models.DecimalField(max_digits=12, decimal_places=0)
    methode = models.CharField(max_length=20, choices=METHODE_CHOICES)
    numero_telephone = models.CharField(max_length=20, blank=True, default="")
    reference_transaction = models.CharField(max_length=50, unique=True)
    date_transaction = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.reference_transaction} - {self.montant} FCFA"
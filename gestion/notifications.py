# gestion/notifications.py
from datetime import timedelta
from django.utils import timezone
from .models import Concession, Exhumation
import requests  # Pour envoyer des SMS via une API

def envoyer_sms(numero, message):
    """Envoie un SMS (à adapter avec ton fournisseur de SMS)"""
    # Exemple avec Twilio ou un service local
    try:
        # response = requests.post("https://api.sms-provider.com/send", data={
        #     "to": numero,
        #     "message": message,
        #     "api_key": "TON_API_KEY"
        # })
        print(f" SMS envoyé à {numero}: {message}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi SMS: {e}")
        return False

def envoyer_notification_concession(concession, client):
    """Envoie une notification lors de la création d'une concession"""
    message = f"NECROPOLIS: Votre concession {concession.type_concession} a été créée. Caveau N°{concession.caveau.numero}. Date fin: {concession.date_fin or 'Perpétuelle'}."
    if client.profil.telephone:
        envoyer_sms(client.profil.telephone, message)
    
    # Email aussi
    from django.core.mail import send_mail
    send_mail(
        subject="Confirmation de concession - NECROPOLIS",
        message=message,
        from_email="noreply@necropolis.cg",
        recipient_list=[client.email],
        fail_silently=True,
    )

def envoyer_alerte_expiration_concessions():
    """Tâche planifiée : alerte les concessions qui expirent bientôt"""
    today = timezone.now().date()
    
    # Alertes à 6 mois, 1 mois, 1 semaine
    for delai_jours, message_template in [(180, "6 mois"), (30, "1 mois"), (7, "1 semaine")]:
        date_limite = today + timedelta(days=delai_jours)
        concessions_a_alert = Concession.objects.filter(
            date_fin__lte=date_limite,
            date_fin__gte=today,
            type_concession__in=['temporaire', 'trentenaire']
        ).select_related('client', 'caveau')
        
        for c in concessions_a_alert:
            message = f"ALERTE NECROPOLIS: Votre concession du caveau N°{c.caveau.numero} expire dans {message_template} (le {c.date_fin}). Contactez-nous pour renouvellement."
            if c.client.profil.telephone:
                envoyer_sms(c.client.profil.telephone, message)
            
            # Email aussi
            from django.core.mail import send_mail
            send_mail(
                subject=f"Alerte expiration concession - {message_template}",
                message=message,
                from_email="noreply@necropolis.cg",
                recipient_list=[c.client.email],
                fail_silently=True,
            )

def notifier_admins_nouvelle_exhumation(exhumation):
    """Notifie les admins qu'une nouvelle demande d'exhumation est en attente"""
    from django.contrib.auth.models import User
    admins = User.objects.filter(profil__role__in=['admin', 'secretariat'])
    
    message = f"NOUVELLE EXHUMATION: Demande #{exhumation.id} pour {exhumation.defunt.nom} {exhumation.defunt.prenom}. Motif: {exhumation.motif}. À valider."
    
    for admin in admins:
        if admin.profil.telephone:
            envoyer_sms(admin.profil.telephone, message)
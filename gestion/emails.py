from django.core.mail import send_mail
from django.conf import settings


def envoyer_confirmation_reservation(reservation):
    sujet = f"Confirmation de réservation - Caveau {reservation.caveau.numero}"
    message = f"""
Bonjour {reservation.client.username},

Votre réservation a été créée avec succès !

Détails :
- Caveau N° : {reservation.caveau.numero}
- Section : {reservation.caveau.section}
- Bloc : {reservation.caveau.bloc}
- Statut : {reservation.statut}
- Défunt : {reservation.defunt.prenom} {reservation.defunt.nom}

Montant à payer : 150 USD

Merci de votre confiance.
Gestion de Cimetière
    """
    send_mail(
        sujet,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [reservation.client.email],
        fail_silently=False,
    )


def envoyer_validation_reservation(reservation):
    sujet = f"Réservation validée - Caveau {reservation.caveau.numero}"
    message = f"""
Bonjour {reservation.client.username},

Votre réservation a été validée !

Le caveau N° {reservation.caveau.numero} est maintenant occupé.

Cordialement,
Administration du Cimetière
    """
    send_mail(
        sujet,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [reservation.client.email],
        fail_silently=False,
    )


def envoyer_code_mfa(email, code):
    sujet = "Code de vérification - Gestion Cimetière"
    message = f"""
Votre code de vérification est : {code}

Ce code expire dans 10 minutes.

Si vous n'avez pas demandé ce code, ignorez cet email.
    """
    send_mail(
        sujet,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
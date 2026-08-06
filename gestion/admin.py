from django.contrib import admin
from .models import (
    Cimetiere, Caveau, Defunt, Reservation, Concession, 
    Exhumation, Profil, Transaction, CodeInvitation, AuditLog, SessionToken
)

@admin.register(Cimetiere)
class CimetiereAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville', 'pays', 'superficie_totale')

@admin.register(Caveau)
class CaveauAdmin(admin.ModelAdmin):
    # SEULEMENT les champs qui existent vraiment dans models.py
    list_display = ('numero', 'section', 'bloc', 'type_caveau', 'statut', 'cimetiere')
    list_filter = ('statut', 'type_caveau', 'cimetiere')
    search_fields = ('numero', 'section', 'bloc')

@admin.register(Defunt)
class DefuntAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'date_deces', 'caveau')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'caveau', 'client', 'statut', 'date_reservation')
    list_filter = ('statut',)

@admin.register(Concession)
class ConcessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'caveau', 'client', 'type_concession', 'date_debut')

@admin.register(Exhumation)
class ExhumationAdmin(admin.ModelAdmin):
    list_display = ('id', 'caveau', 'defunt', 'statut', 'date_demande')

@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'statut', 'cimetiere')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'montant', 'methode', 'date_transaction')

@admin.register(CodeInvitation)
class CodeInvitationAdmin(admin.ModelAdmin):
    list_display = ('code', 'cimetiere', 'role_autorise', 'utilise')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'utilisateur', 'action', 'objet_type')

@admin.register(SessionToken)
class SessionTokenAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'cle', 'date_creation')
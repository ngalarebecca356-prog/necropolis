from django.contrib import admin
from .models import Caveau, Defunt, Reservation, Concession, Exhumation, Profil, AuditLog, Cimetiere
from datetime import date

@admin.register(Cimetiere)
class CimetiereAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville', 'pays', 'superficie_totale', 'nombre_places_estime', 'admin_createur', 'date_creation')
    search_fields = ('nom', 'ville', 'pays')
    readonly_fields = ('mot_de_passe_acces',)

@admin.register(Caveau)
class CaveauAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'statut')
    list_filter = ('statut', 'section', 'bloc')
    search_fields = ('numero', 'localisation')

@admin.register(Defunt)
class DefuntAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'date_deces', 'caveau')
    search_fields = ('nom', 'prenom')

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('client', 'caveau', 'defunt', 'statut', 'date_reservation')
    list_filter = ('statut',)
    search_fields = ('client',)

@admin.register(Concession)
class ConcessionAdmin(admin.ModelAdmin):
    list_display = ('caveau', 'beneficiaire', 'client', 'type_concession', 'date_debut', 'date_fin', 'montant', 'jours_restants')
    list_filter = ('type_concession', 'renouvele')
    search_fields = ('beneficiaire', 'client', 'caveau__numero')
    date_hierarchy = 'date_fin'

    def jours_restants(self, obj):
        if obj.date_fin:
            delta = (obj.date_fin - date.today()).days
            if delta < 0:
                return "Expiré"
            return f"{delta} j"
        return "-"
    jours_restants.short_description = "Reste"

@admin.register(Exhumation)
class ExhumationAdmin(admin.ModelAdmin):
    list_display = ('defunt', 'caveau', 'date_demande', 'statut')
    list_filter = ('statut',)

from .models import Profil, AuditLog

@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'statut', 'date_creation')
    list_filter = ('role', 'statut')
    search_fields = ('user__username', 'user__email')
    actions = ['valider_comptes', 'refuser_comptes']

    def valider_comptes(self, request, queryset):
        queryset.update(statut='valide')
    valider_comptes.short_description = "Valider les comptes selectionnes"

    def refuser_comptes(self, request, queryset):
        queryset.update(statut='refuse')
    refuser_comptes.short_description = "Refuser les comptes selectionnes"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'utilisateur', 'action', 'objet_type', 'objet_id')
    list_filter = ('action', 'objet_type')
    search_fields = ('utilisateur__username', 'action')
    date_hierarchy = 'date'
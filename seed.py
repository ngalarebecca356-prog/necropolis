import os
import django
from django.contrib.auth.hashers import make_password

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cimetiere.settings')
django.setup()

from django.contrib.auth.models import User
from gestion.models import Cimetiere, Caveau, Profil

def seed_database():
    print(" Nettoyage des anciennes données...")
    Caveau.objects.all().delete()
    Cimetiere.objects.all().delete()
    User.objects.all().delete()
    # Pas besoin de supprimer les Profils car ils sont liés aux Users
    # et seront supprimés automatiquement par la cascade

    print("👤 Création du compte Administrateur...")
    admin = User.objects.create_user(
        username='admin', 
        password='admin1234', 
        email='stelliangala@gmail.com'
    )
    
    # Le profil est créé automatiquement par le signal post_save
    # On le met à jour avec les bonnes valeurs
    admin.profil.role = 'admin'
    admin.profil.statut = 'valide'
    admin.profil.save()

    print("🏛️ Création des cimetières avec délimitations réelles...")
    
    # 1. Cimetière de Vindoulou (Pointe-Noire)
    cim1 = Cimetiere.objects.create(
        nom="Cimetière Municipal de Vindoulou",
        ville="Pointe-Noire",
        quartier="Vindoulou",
        pays="République du Congo",
        latitude=-4.7833, longitude=11.8667,
        # Rectangle de délimitation (environ 200m x 300m)
        limite_nord=-4.7815, limite_sud=-4.7851,
        limite_est=11.8685, limite_ouest=11.8649,
        superficie_totale=6000,
        mot_de_passe_acces=make_password("cimetiere123"),
        admin_createur=admin
    )

    # 2. Cimetière de Ouenzé (Brazzaville)
    cim2 = Cimetiere.objects.create(
        nom="Cimetière de Ouenzé",
        ville="Brazzaville",
        quartier="Ouenzé",
        pays="République du Congo",
        latitude=-4.2500, longitude=15.2833,
        # Rectangle de délimitation
        limite_nord=-4.2480, limite_sud=-4.2520,
        limite_est=15.2855, limite_ouest=15.2811,
        superficie_totale=8000,
        mot_de_passe_acces=make_password("cimetiere123"),
        admin_createur=admin
    )

    # 3. Cimetière de la Paix (Brazzaville)
    cim3 = Cimetiere.objects.create(
        nom="Cimetière de la Paix",
        ville="Brazzaville",
        quartier="Makélékélé",
        pays="République du Congo",
        latitude=-4.2700, longitude=15.2600,
        # Rectangle de délimitation
        limite_nord=-4.2680, limite_sud=-4.2720,
        limite_est=15.2622, limite_ouest=15.2578,
        superficie_totale=5000,
        mot_de_passe_acces=make_password("cimetiere123"),
        admin_createur=admin
    )

    print("⚰️ Ajout de quelques caveaux pour tester la carte...")
    # Caveaux pour Vindoulou
    Caveau.objects.create(cimetiere=cim1, numero="V-001", section="A", bloc="1", statut="disponible", localisation=None)
    Caveau.objects.create(cimetiere=cim1, numero="V-002", section="A", bloc="1", statut="occupe", localisation=None)
    
    # Caveaux pour Ouenzé
    Caveau.objects.create(cimetiere=cim2, numero="O-001", section="B", bloc="2", statut="disponible", localisation=None)
    Caveau.objects.create(cimetiere=cim2, numero="O-002", section="B", bloc="2", statut="reserve", localisation=None)

    print("✅ Base de données remplie avec succès !")
    print("🔑 Identifiants Admin : admin / admin1234")
    print(" Mot de passe cimetières : cimetiere123")

if __name__ == "__main__":
    seed_database()
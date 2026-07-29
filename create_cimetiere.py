import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cimetiere.settings')
django.setup()

from django.contrib.auth.models import User
from gestion.models import Cimetiere
from django.contrib.auth.hashers import make_password

try:
    jude = User.objects.get(username='jude')
    
    cim = Cimetiere.objects.create(
        nom="Cimetière Municipal de Lumumba",
        ville="Pointe-Noire",
        quartier="Lumumba",
        pays="République du Congo",
        latitude=-4.7441,
        longitude=11.9226,
        limite_nord=-4.7420,
        limite_sud=-4.7462,
        limite_est=11.9250,
        limite_ouest=11.9202,
        superficie_totale=6000,
        mot_de_passe_acces=make_password("cimetiere123"),
        admin_createur=jude
    )
    
    print("✅ SUCCÈS : Cimetière créé et lié à jude !")
except User.DoesNotExist:
    print("❌ ERREUR : L'utilisateur 'jude' n'existe pas.")
except Exception as e:
    print(f"❌ ERREUR : {e}")
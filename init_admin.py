import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cimetiere.settings')
django.setup()

from django.contrib.auth.models import User

username = 'admin'
email = 'ngalarebecca356@gmail.com'
password = 'admin123'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✅ Superutilisateur '{username}' créé avec succès !")
else:
    print(f"ℹ️ Le superutilisateur '{username}' existe déjà.")
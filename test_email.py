import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cimetiere.settings')
django.setup()

from django.core.mail import send_mail

try:
       send_mail(
           'Test NECROPOLIS', 
           'Si tu reçois ceci, la configuration SMTP fonctionne !', 
           'ngalarebecca356@gmail.com', 
           ['ngalarebecca356@gmail.com'], 
           fail_silently=False
       )
       print("✅ Email envoyé avec succès ! Vérifie ta boîte mail.")
except Exception as e:
       print(f"❌ ERREUR SMTP : {e}") 
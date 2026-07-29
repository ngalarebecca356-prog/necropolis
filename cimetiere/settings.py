from pathlib import Path
import os
import platform
from dotenv import load_dotenv  # <-- AJOUTE CETTE LIGNE

# Charger les variables du fichier .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Lire la clé secrète depuis le .env
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-cimetiere-gestion-2026-secret-key')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-cimetiere-gestion-2026-secret-key'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Chemins GDAL pour Windows seulement
if platform.system() == 'Windows':
    GDAL_LIBRARY_PATH = r'C:\Users\hp\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages\osgeo\gdal.dll'
    GEOS_LIBRARY_PATH = r'C:\Users\hp\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\site-packages\osgeo\geos_c.dll'

# Apps et base de données selon l'environnement
ON_RAILWAY = os.environ.get("USE_SQLITE") is not None

if ON_RAILWAY:
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'ninja',
        'gestion',
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.mfa',
    ]
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    INSTALLED_APPS = [
        'corsheaders',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.gis',
        'ninja',
        'gestion',
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.mfa',
    ]
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': 'cimetiere',
            'USER': 'postgres',
            'PASSWORD': '1234',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'cimetiere.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cimetiere.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Brazzaville'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'

SITE_ID = 1

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
MFA_TOTP_ISSUER = 'Gestion Cimetiere'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'Gestion Cimetiere <{os.getenv("EMAIL_HOST_USER")}>'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_REDIRECT_URL = '/admin/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/accounts/login/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Configuration CORS pour permettre les requêtes depuis la carte
CORS_ALLOW_ALL_ORIGINS = True  # En développement uniquement
CORS_ALLOW_CREDENTIALS = True

# Ajouter 'corsheaders' dans INSTALLED_APPS si pas déjà fait
# Et dans MIDDLEWARE, ajouter 'corsheaders.middleware.CorsMiddleware' en PREMIER

import dj_database_url
# Si Render fournit une base de données, on l'utilise. Sinon, on garde SQLite.
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            ssl_require=True
        )
    }

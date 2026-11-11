"""Configuration Django du projet QCM en direct (V1)."""

import os
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-seulement-a-changer")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Hôte public de l'URL encodée dans le QR code (format « ip:port »).
# Vide : on garde request.build_absolute_uri (démo locale sur l'ordinateur).
QCM_LAN_HOST = os.environ.get("QCM_LAN_HOST", "").strip()


def _hotes_locaux() -> list[str]:
    """Noms et adresses IPv4 du serveur, pour l'accès téléphone en Wi-Fi local."""
    hotes = {"localhost", "127.0.0.1", "[::1]"}
    try:
        # Un connect() UDP n'envoie aucun paquet : il révèle l'IP de l'interface
        # qui porte la route par défaut, c'est-à-dire l'IP LAN du serveur.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonde:
            sonde.connect(("8.8.8.8", 80))
            hotes.add(sonde.getsockname()[0])
    except OSError:
        pass
    try:
        nom = socket.gethostname()
        if nom:
            hotes.add(nom)
            for info in socket.getaddrinfo(nom, None):
                adresse = info[4][0]
                if ":" not in adresse:
                    hotes.add(adresse)
    except OSError:
        pass
    return sorted(hotes)


# En développement/démo, on accepte les accès depuis le réseau local (téléphones).
# Hors DEBUG, DJANGO_ALLOWED_HOSTS (liste séparée par des virgules) est complété
# par les adresses locales détectées, pour que l'iPhone puisse joindre le serveur
# sur le Wi-Fi sans configuration supplémentaire.
if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = sorted(
        {
            h.strip()
            for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
            if h.strip()
        }
        | set(_hotes_locaux())
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "qcm",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # Base de test sur fichier : permet de vérifier la persistance après
        # fermeture/réouverture des connexions (simulation de redémarrage).
        "TEST": {"NAME": BASE_DIR / ".test_db.sqlite3"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"

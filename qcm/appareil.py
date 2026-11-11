"""Cookie d'appareil partagé entre les onglets (httpOnly).

Le jeton de connexion élève vit dans ``sessionStorage`` (isolé par onglet) ;
l'identité de l'appareil, elle, doit être partagée entre les onglets pour
empêcher qu'un second élève se connecte depuis le même navigateur. Elle est
portée par ce cookie httpOnly, généré côté serveur et associé au
``Participant`` de la session (un seul participant actif par cookie/séance).
"""

import uuid

from django.conf import settings

NOM_COOKIE_APPAREIL = "cookie_appareil"
DUREE_COOKIE_APPAREIL = 60 * 60 * 24 * 30


def lire_cookie_appareil(request) -> tuple[uuid.UUID, bool]:
    """Retourne (cookie, nouveau) ; génère un identifiant si absent/invalide."""
    valeur = request.COOKIES.get(NOM_COOKIE_APPAREIL)
    if valeur:
        try:
            return uuid.UUID(str(valeur)), False
        except (TypeError, ValueError, AttributeError):
            pass
    return uuid.uuid4(), True


def poser_cookie_appareil(reponse, valeur: uuid.UUID) -> None:
    reponse.set_cookie(
        NOM_COOKIE_APPAREIL,
        str(valeur),
        max_age=DUREE_COOKIE_APPAREIL,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )

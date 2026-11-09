"""Routes publiques, élève et professeur."""

from django.urls import path

from qcm import api, views

app_name = "qcm"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("rejoindre/", views.rejoindre_saisie, name="rejoindre_saisie"),
    path("rejoindre/<str:code>/", views.rejoindre, name="rejoindre"),
    path("eleve/<str:code>/", views.eleve, name="eleve"),
    path("tableau/<str:code>/", views.tableau, name="tableau"),
    path("api/rejoindre/", api.rejoindre, name="api_rejoindre"),
    path("api/etat/", api.etat_eleve, name="api_etat"),
    path("api/repondre/", api.repondre, name="api_repondre"),
    path("api/etat_prof/", api.etat_prof, name="api_etat_prof"),
    path("api/piloter/", api.piloter, name="api_piloter"),
]

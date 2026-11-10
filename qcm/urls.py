"""Routes publiques, élève et professeur."""

from django.urls import path

from qcm import api, views

app_name = "qcm"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("rejoindre/", views.rejoindre_saisie, name="rejoindre_saisie"),
    path("rejoindre/<str:code>/", views.rejoindre, name="rejoindre"),
    path("eleve/<str:code>/", views.eleve, name="eleve"),
    path(
        "tableau/<str:code>/presentation/",
        views.presentation,
        name="presentation",
    ),
    path("tableau/<str:code>/", views.tableau, name="tableau"),
    path("session/creer/", views.session_creer, name="session_creer"),
    path(
        "groupe/<int:groupe_id>/importer-eleves/",
        views.importer_eleves,
        name="importer_eleves",
    ),
    path(
        "groupe/<int:groupe_id>/identifiants/<str:format>/",
        views.exporter_identifiants,
        name="exporter_identifiants",
    ),
    path(
        "session/<str:code>/participants/",
        views.participants,
        name="participants",
    ),
    path(
        "session/<str:code>/participants/<int:participant_id>/reinitialiser/",
        views.reinitialiser_appareil,
        name="reinitialiser_appareil",
    ),
    path("session/<str:code>/", views.session_initiale, name="session_initiale"),
    path("resultats/<str:code>/", views.resultats, name="resultats"),
    path("api/rejoindre/", api.rejoindre, name="api_rejoindre"),
    path("api/etat/", api.etat_eleve, name="api_etat"),
    path("api/repondre/", api.repondre, name="api_repondre"),
    path(
        "api/etat_participants/",
        api.etat_participants,
        name="api_etat_participants",
    ),
    path("api/etat_prof/", api.etat_prof, name="api_etat_prof"),
    path("api/piloter/", api.piloter, name="api_piloter"),
]

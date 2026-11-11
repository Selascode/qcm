"""Parcours professeur dans l'admin : créer une séance, ouvrir le tableau."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from qcm.import_json import importer_quiz
from qcm.models import Groupe, Participant, Session, Student
from qcm.tests.helpers import donnees_quiz

pytestmark = pytest.mark.django_db


def test_admin_cree_une_session_avec_code_et_lien_tableau(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(1, 1), administrateur)
    client.force_login(administrateur)

    formulaire = client.get("/admin/qcm/session/add/")
    assert formulaire.status_code == 200

    enregistrement = client.post(
        "/admin/qcm/session/add/",
        {"quiz": quiz.pk, "_save": "Enregistrer"},
    )
    assert enregistrement.status_code == 302

    session = Session.objects.get(quiz=quiz)
    assert len(session.code_session) == 6
    assert session.statut == Session.STATUT_ATTENTE

    page = client.get(f"/admin/qcm/session/{session.pk}/change/")
    assert page.status_code == 200

    liste = client.get("/admin/qcm/session/")
    assert liste.status_code == 200
    assert f"/tableau/{session.code_session}/" in liste.content.decode()


def test_admin_participants_affiche_la_colonne_groupe(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-groupe",
        email="admin-groupe@example.com",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(1, 1), administrateur)
    session = Session.objects.create(quiz=quiz)
    Participant.objects.create(session=session)
    client.force_login(administrateur)

    liste = client.get("/admin/qcm/participant/")

    assert liste.status_code == 200
    contenu = liste.content.decode()
    assert "Groupe" in contenu
    assert "—" in contenu


def test_admin_inline_groupe_ajoute_un_eleve(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-inline",
        email="admin-inline@example.com",
        password="secret",
    )
    groupe = Groupe.objects.create(nom="ISIA4", proprietaire=administrateur)
    client.force_login(administrateur)

    url = reverse("admin:qcm_groupe_change", args=[groupe.pk])
    reponse = client.post(
        url,
        {
            "nom": "ISIA4",
            "proprietaire": str(administrateur.pk),
            "etudiants-TOTAL_FORMS": "1",
            "etudiants-INITIAL_FORMS": "0",
            "etudiants-MIN_NUM_FORMS": "0",
            "etudiants-MAX_NUM_FORMS": "1000",
            "etudiants-0-nom": "Dupont",
            "etudiants-0-prenom": "Marie",
            "etudiants-0-code_etudiant": "",
            "_save": "Enregistrer",
        },
    )

    assert reponse.status_code == 302
    eleve = Student.objects.get(groupe=groupe)
    assert eleve.nom == "Dupont"
    assert eleve.prenom == "Marie"
    assert eleve.code_etudiant == "MARIE-DUP00"

    page = client.get(url)
    contenu = page.content.decode()
    assert "Dupont" in contenu
    assert "MARIE-DUP00" in contenu

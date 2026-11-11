"""Groupes, élèves et création de séance rattachée à un groupe (V2)."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse

from qcm.import_questions import importer_quiz
from qcm.models import Groupe, Participant, Session
from qcm.tests.helpers import creer_eleve, creer_groupe, donnees_quiz

pytestmark = pytest.mark.django_db


def test_creation_seance_avec_groupe(client, proprietaire, groupe):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    client.force_login(proprietaire)

    page = client.get(reverse("qcm:session_creer"))
    assert page.status_code == 200
    assert "ISIA4" in page.content.decode()

    reponse = client.post(
        reverse("qcm:session_creer"),
        {"quiz": quiz.pk, "groupe": groupe.pk},
    )

    assert reponse.status_code == 302
    session = Session.objects.get(quiz=quiz)
    assert session.groupe == groupe


def test_creation_seance_sans_groupe(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    client.force_login(proprietaire)

    client.post(reverse("qcm:session_creer"), {"quiz": quiz.pk, "groupe": ""})

    assert Session.objects.get(quiz=quiz).groupe is None


def test_creation_seance_refuse_le_groupe_d_un_autre(
    client, proprietaire, autre_proprietaire
):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    groupe_autre = creer_groupe(autre_proprietaire, nom="Autre")
    client.force_login(proprietaire)

    reponse = client.post(
        reverse("qcm:session_creer"),
        {"quiz": quiz.pk, "groupe": groupe_autre.pk},
    )

    assert reponse.status_code == 404
    assert not Session.objects.exists()


def test_un_seul_participant_par_eleve_et_par_seance(groupe):
    quiz = importer_quiz(donnees_quiz(1, 1), groupe.proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    student = creer_eleve(groupe)
    Participant.objects.create(session=session, student=student)

    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.create(session=session, student=student)


def test_admin_participant_affiche_le_vrai_groupe(client, proprietaire, groupe):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-groupe-v2",
        email="admin-groupe-v2@example.com",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    student = creer_eleve(groupe)
    Participant.objects.create(session=session, student=student)
    client.force_login(administrateur)

    liste = client.get("/admin/qcm/participant/")

    assert liste.status_code == 200
    assert "ISIA4" in liste.content.decode()


def test_admin_groupe_accessible(client, proprietaire):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-groupes",
        email="admin-groupes@example.com",
        password="secret",
    )
    Groupe.objects.create(nom="Groupe admin", proprietaire=proprietaire)
    client.force_login(administrateur)

    liste = client.get("/admin/qcm/groupe/")

    assert liste.status_code == 200
    assert "Groupe admin" in liste.content.decode()

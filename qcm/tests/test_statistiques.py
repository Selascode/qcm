"""Statistiques de fin d'étape dans le mode Présentation (V4)."""

import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from qcm import services
from qcm.import_questions import importer_quiz
from qcm.models import Answer, Participant, Session
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
)

pytestmark = pytest.mark.django_db


def preparer(proprietaire, nb_etapes=1, questions_par_etape=1):
    quiz = importer_quiz(
        donnees_quiz(nb_etapes, questions_par_etape), proprietaire
    )
    return quiz, creer_session(quiz)


def ajouter_reponse(session, participant, question, lettres):
    Answer.objects.create(
        session=session,
        participant=participant,
        question=question,
        choix_selectionnes=lettres,
        id_client=uuid.uuid4(),
    )


def test_statistiques_par_choix_et_bonne_reponse(proprietaire):
    quiz, session = preparer(proprietaire)
    session = demarrer(session)
    question = quiz.questions.get(uid="E1Q1")
    participants = [
        Participant.objects.create(session=session) for _ in range(3)
    ]
    ajouter_reponse(session, participants[0], question, ["A"])
    ajouter_reponse(session, participants[1], question, ["A"])
    ajouter_reponse(session, participants[2], question, ["B"])

    statistiques = services.statistiques_etape(session)

    assert len(statistiques) == 1
    assert statistiques[0]["nb_reponses"] == 3
    choix = {ligne["lettre"]: ligne for ligne in statistiques[0]["choix"]}
    assert choix["A"]["nombre"] == 2
    assert choix["A"]["pourcentage"] == 66.7
    assert choix["A"]["largeur"] == "66.7"
    assert choix["A"]["pourcentage_affiche"] == "67"
    assert choix["A"]["est_correct"] is True
    assert choix["B"]["nombre"] == 1
    assert choix["B"]["pourcentage"] == 33.3
    assert choix["B"]["est_correct"] is False
    assert choix["C"]["nombre"] == 0
    assert choix["C"]["pourcentage"] == 0.0


def test_statistiques_sans_reponse(proprietaire):
    _, session = preparer(proprietaire)
    session = demarrer(session)

    statistiques = services.statistiques_etape(session)

    assert statistiques[0]["nb_reponses"] == 0
    assert all(
        ligne["pourcentage"] == 0.0 for ligne in statistiques[0]["choix"]
    )


def test_statistiques_choix_multiple(proprietaire):
    quiz, session = preparer(proprietaire)
    session = demarrer(session)
    question = quiz.questions.get(uid="E1Q1")
    question.type = question.TYPE_MULTIPLE
    question.save(update_fields=["type"])
    participants = [
        Participant.objects.create(session=session) for _ in range(2)
    ]
    ajouter_reponse(session, participants[0], question, ["A", "B"])
    ajouter_reponse(session, participants[1], question, ["A"])

    statistiques = services.statistiques_etape(session)

    choix = {ligne["lettre"]: ligne for ligne in statistiques[0]["choix"]}
    assert choix["A"]["pourcentage"] == 100.0
    assert choix["B"]["pourcentage"] == 50.0
    assert choix["C"]["pourcentage"] == 0.0


def test_presentation_affiche_les_barres_en_pause(client, proprietaire):
    quiz, session = preparer(proprietaire)
    session = demarrer(session)
    question = quiz.questions.get(uid="E1Q1")
    participants = [
        Participant.objects.create(session=session) for _ in range(2)
    ]
    ajouter_reponse(session, participants[0], question, ["A"])
    ajouter_reponse(session, participants[1], question, ["B"])
    services.mettre_en_pause(session)
    client.force_login(proprietaire)

    reponse = client.get(f"/tableau/{session.code_session}/presentation/")
    contenu = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'class="statistiques-etape"' in contenu
    assert "Répartition des réponses" in contenu
    assert "stat-barre" in contenu
    assert "width: 50.0%" in contenu
    assert "stat-ligne correcte" in contenu
    assert "Bonne réponse" in contenu
    assert "✓" in contenu
    assert "E1Q1" in contenu
    assert "grille-questions" not in contenu


def test_presentation_sans_stats_pendant_l_etape(client, proprietaire):
    _, session = preparer(proprietaire)
    demarrer(session)
    client.force_login(proprietaire)

    contenu = client.get(
        f"/tableau/{session.code_session}/presentation/"
    ).content.decode()

    assert "statistiques-etape" not in contenu
    assert "grille-questions" in contenu


def test_presentation_stats_apres_ends_at_avant_auto_avance(
    client, proprietaire
):
    _, session = preparer(proprietaire)
    demarrer(session)
    Session.objects.filter(pk=session.pk).update(
        ends_at=timezone.now() - timedelta(seconds=1)
    )
    client.force_login(proprietaire)

    contenu = client.get(
        f"/tableau/{session.code_session}/presentation/"
    ).content.decode()
    session.refresh_from_db()

    assert "statistiques-etape" in contenu
    assert session.statut == Session.STATUT_EN_COURS
    assert session.etape_courante == 1


def test_presentation_terminee_sans_stats(client, proprietaire):
    _, session = preparer(proprietaire)
    demarrer(session)
    services.terminer_session(session)
    client.force_login(proprietaire)

    contenu = client.get(
        f"/tableau/{session.code_session}/presentation/"
    ).content.decode()

    assert "Séance terminée" in contenu
    assert "statistiques-etape" not in contenu


def test_presentation_protegee(client, proprietaire, autre_proprietaire):
    _, session = preparer(proprietaire)
    url = f"/tableau/{session.code_session}/presentation/"

    assert Client().get(url).status_code == 302

    client.force_login(autre_proprietaire)
    assert client.get(url).status_code == 403

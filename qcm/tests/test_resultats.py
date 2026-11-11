"""Résultats : notes par élève, plancher 0 et taux de réussite par question."""

import uuid

import pytest
from django.urls import reverse

from qcm.import_questions import importer_quiz
from qcm.models import Answer, Participant, Session
from qcm.resultats import calculer_resultats
from qcm.tests.helpers import creer_eleve

pytestmark = pytest.mark.django_db


def donnees_resultats() -> dict:
    return {
        "titre": "Résultats",
        "questions": [
            {
                "uid": "Q1",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Question 1",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "bonne", "correct": True},
                    {"lettre": "B", "texte": "mauvaise", "correct": False},
                ],
            },
            {
                "uid": "Q2",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Question 2",
                "type": "multiple",
                "choix": [
                    {"lettre": "A", "texte": "bonne 1", "correct": True},
                    {"lettre": "B", "texte": "bonne 2", "correct": True},
                    {"lettre": "C", "texte": "mauvaise", "correct": False},
                ],
            },
        ],
    }


def _preparer(proprietaire, groupe):
    quiz = importer_quiz(donnees_resultats(), proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    marie = creer_eleve(groupe, nom="Dupont", prenom="Marie", code_etudiant="MD0001")
    paul = creer_eleve(groupe, nom="Martin", prenom="Paul", code_etudiant="PM0002")
    participant_marie = Participant.objects.create(session=session, student=marie)
    participant_paul = Participant.objects.create(session=session, student=paul)
    questions = {question.uid: question for question in quiz.questions.all()}
    Answer.objects.create(
        session=session,
        participant=participant_marie,
        question=questions["Q1"],
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_marie,
        question=questions["Q2"],
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_paul,
        question=questions["Q1"],
        choix_selectionnes=["B"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_paul,
        question=questions["Q2"],
        choix_selectionnes=["A", "B"],
        id_client=uuid.uuid4(),
    )
    return session, participant_marie, participant_paul


def test_notes_par_eleve_et_plancher_zero(proprietaire, groupe):
    session, participant_marie, participant_paul = _preparer(proprietaire, groupe)

    resultats = calculer_resultats(session)

    par_participant = {
        ligne["participant"].pk: ligne for ligne in resultats["lignes_participants"]
    }
    assert par_participant[participant_marie.pk]["total"] == pytest.approx(1.5)
    assert par_participant[participant_paul.pk]["total"] == pytest.approx(0.0)
    assert resultats["lignes_participants"][0]["participant"] == participant_marie


def test_taux_de_reussite_par_question(proprietaire, groupe):
    session, _, _ = _preparer(proprietaire, groupe)

    resultats = calculer_resultats(session)
    stats = {stat["question"].uid: stat for stat in resultats["stats_questions"]}

    assert stats["Q1"]["nb_reponses"] == 2
    assert stats["Q1"]["nb_correctes"] == 1
    assert stats["Q1"]["taux_reussite"] == pytest.approx(50.0)
    assert stats["Q2"]["nb_reponses"] == 2
    assert stats["Q2"]["nb_correctes"] == 1
    assert stats["Q2"]["taux_reussite"] == pytest.approx(50.0)


def test_penalite_desactivee(proprietaire, groupe):
    session, participant_marie, participant_paul = _preparer(proprietaire, groupe)
    session.quiz.penalite_active = False
    session.quiz.save(update_fields=["penalite_active"])

    resultats = calculer_resultats(session)
    par_participant = {
        ligne["participant"].pk: ligne for ligne in resultats["lignes_participants"]
    }

    assert par_participant[participant_marie.pk]["total"] == pytest.approx(1.5)
    assert par_participant[participant_paul.pk]["total"] == pytest.approx(1.0)


def test_question_sans_reponse_a_un_taux_nul(proprietaire, groupe):
    quiz = importer_quiz(donnees_resultats(), proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)

    resultats = calculer_resultats(session)

    for stat in resultats["stats_questions"]:
        assert stat["nb_reponses"] == 0
        assert stat["taux_reussite"] is None


def test_vue_resultats_accessible_au_proprietaire(
    client, proprietaire, groupe
):
    session, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.get(reverse("qcm:resultats", args=[session.code_session]))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "Notes par élève" in contenu
    assert "Taux de réussite par question" in contenu
    assert "Dupont" in contenu
    assert "Martin" in contenu


def test_vue_resultats_refusee_a_un_autre_professeur(
    client, proprietaire, autre_proprietaire, groupe
):
    session, _, _ = _preparer(proprietaire, groupe)
    client.force_login(autre_proprietaire)

    reponse = client.get(reverse("qcm:resultats", args=[session.code_session]))

    assert reponse.status_code == 403


def test_vue_resultats_anonyme_redirige(client, proprietaire, groupe):
    session, _, _ = _preparer(proprietaire, groupe)

    reponse = client.get(reverse("qcm:resultats", args=[session.code_session]))

    assert reponse.status_code == 302

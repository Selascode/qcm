"""Scénario V3 : QCM composé de questions issues de plusieurs ensembles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from qcm import services
from qcm.models import Participant, Question, QuestionSet, Quiz, QuizQuestion, Session

pytestmark = pytest.mark.django_db


def _question(question_set, uid, duree_s=60):
    return Question.objects.create(
        set=question_set,
        uid=uid,
        enonce=f"Énoncé {uid}",
        type=Question.TYPE_UNIQUE,
        duree_s=duree_s,
    )


def _quiz_avec_selection(proprietaire):
    set_a = QuestionSet.objects.create(nom="CM 3", proprietaire=proprietaire)
    set_b = QuestionSet.objects.create(nom="TD 2", proprietaire=proprietaire)
    questions = [
        _question(set_a, "Q1", 60),
        _question(set_b, "Q2", 60),
        _question(set_a, "Q3", 120),
        _question(set_b, "Q4", 60),
        _question(set_a, "Q5", 60),
    ]
    quiz = Quiz.objects.create(
        titre="Séance mélangée", proprietaire=proprietaire, duree_s=60
    )
    QuizQuestion.objects.bulk_create(
        [
            QuizQuestion(quiz=quiz, question=question, position=position)
            for position, question in enumerate(questions, start=1)
        ]
    )
    return quiz, questions


def test_selection_de_cinq_questions_de_sets_differents(proprietaire):
    quiz, _ = _quiz_avec_selection(proprietaire)
    session = Session.objects.create(quiz=quiz)

    assert [question.uid for question in services.questions_du_quiz(quiz)] == [
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "Q5",
    ]
    assert services.nombre_etapes(session) == 5
    assert [
        question.uid
        for question in services.questions_de_l_etape(session, 1)
    ] == ["Q1", "Q2", "Q3", "Q4"]
    assert [
        question.uid
        for question in services.questions_de_l_etape(session, 5)
    ] == ["Q5"]


def test_la_seance_demarre_et_rotation_des_couleurs(proprietaire):
    quiz, _ = _quiz_avec_selection(proprietaire)
    session = Session.objects.create(quiz=quiz)
    participants = [
        Participant.objects.create(session=session, couleur_assignee=couleur)
        for couleur in (1, 2, 3, 4)
    ]

    moment = timezone.now()
    session = services.demarrer_session(session, maintenant=moment)

    assert session.statut == Session.STATUT_EN_COURS
    assert session.etape_courante == 1
    assert session.ends_at == moment + timedelta(seconds=120)
    assert [
        services.question_courante_pour(session, participant).uid
        for participant in participants
    ] == ["Q1", "Q2", "Q3", "Q4"]

    session = services.etape_suivante(session)

    assert session.etape_courante == 2
    assert [
        services.question_courante_pour(session, participant).uid
        for participant in participants
    ] == ["Q2", "Q3", "Q4", "Q1"]


def test_duree_etape_est_le_maximum_du_quiz_et_des_questions(proprietaire):
    ensemble = QuestionSet.objects.create(
        nom="Durées", proprietaire=proprietaire
    )
    rapide = _question(ensemble, "RAPIDE", 30)
    longue = _question(ensemble, "LONGUE", 120)
    quiz = Quiz.objects.create(
        titre="Durées", proprietaire=proprietaire, duree_s=60
    )
    QuizQuestion.objects.create(quiz=quiz, question=rapide, position=1)
    session = Session.objects.create(quiz=quiz)

    moment = timezone.now()
    session = services.demarrer_session(session, maintenant=moment)
    assert session.ends_at == moment + timedelta(seconds=60)

    QuizQuestion.objects.create(quiz=quiz, question=longue, position=2)
    session = Session.objects.create(quiz=quiz)
    moment = timezone.now()
    session = services.demarrer_session(session, maintenant=moment)
    assert session.ends_at == moment + timedelta(seconds=120)


def test_couleur_est_la_position_dans_le_paquet(proprietaire):
    quiz, _ = _quiz_avec_selection(proprietaire)
    session = Session.objects.create(quiz=quiz)
    question = quiz.quiz_questions.get(position=3).question

    assert (
        services.position_question_dans_etape(session, 1, question) == 3
    )
    assert services.position_question_dans_etape(session, 5, question) is None

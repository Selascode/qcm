"""Data migration V3 : les questions existantes rejoignent la banque."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

AVANT = [("qcm", "0009_participant_cookie_appareil_and_more")]
APRES = [("qcm", "0012_finaliser_la_banque")]


def _executeur() -> MigrationExecutor:
    executeur = MigrationExecutor(connection)
    executeur.loader.build_graph()
    return executeur


def test_les_questions_existantes_rejoignent_le_set_par_defaut():
    executeur = _executeur()
    try:
        executeur.migrate(AVANT)
        anciens = executeur.loader.project_state(AVANT).apps
        Utilisateur = anciens.get_model("auth", "User")
        Quiz = anciens.get_model("qcm", "Quiz")
        Step = anciens.get_model("qcm", "Step")
        Question = anciens.get_model("qcm", "Question")
        Choice = anciens.get_model("qcm", "Choice")

        professeur = Utilisateur.objects.create(username="prof-migration")
        sans_questions = Utilisateur.objects.create(username="prof-vide")

        quiz1 = Quiz.objects.create(titre="Quiz 1", proprietaire=professeur)
        step1 = Step.objects.create(quiz=quiz1, numero=1, duree_s=90)
        q1 = Question.objects.create(
            quiz=quiz1,
            step=step1,
            uid="Q1",
            enonce="Énoncé 1",
            type="unique",
            ordre=1,
            couleur_slot=1,
        )
        q2 = Question.objects.create(
            quiz=quiz1,
            step=step1,
            uid="Q2",
            enonce="Énoncé 2",
            type="unique",
            ordre=2,
            couleur_slot=2,
        )
        Choice.objects.create(
            question=q1,
            lettre="A",
            texte="Bonne",
            est_correct=True,
            position=0,
        )
        Choice.objects.create(
            question=q1,
            lettre="B",
            texte="Mauvaise",
            est_correct=False,
            position=1,
        )

        quiz2 = Quiz.objects.create(titre="Quiz 2", proprietaire=professeur)
        step2 = Step.objects.create(quiz=quiz2, numero=1, duree_s=120)
        q3 = Question.objects.create(
            quiz=quiz2,
            step=step2,
            uid="Q1",
            enonce="Autre Q1",
            type="multiple",
            ordre=1,
            couleur_slot=1,
        )

        executeur = _executeur()
        executeur.migrate(APRES)
        nouveaux = executeur.loader.project_state(APRES).apps
        QuestionSet = nouveaux.get_model("qcm", "QuestionSet")
        QuestionV3 = nouveaux.get_model("qcm", "Question")
        QuizV3 = nouveaux.get_model("qcm", "Quiz")
        QuizQuestion = nouveaux.get_model("qcm", "QuizQuestion")

        ensembles = QuestionSet.objects.filter(proprietaire_id=professeur.pk)
        assert ensembles.count() == 1
        ensemble = ensembles.get()
        assert ensemble.nom == "Questions existantes"
        assert not QuestionSet.objects.filter(
            proprietaire_id=sans_questions.pk
        ).exists()

        questions = {
            question.pk: question
            for question in QuestionV3.objects.filter(set=ensemble)
        }
        assert len(questions) == 3
        assert {question.set_id for question in questions.values()} == {
            ensemble.pk
        }

        assert questions[q1.pk].uid == "Q1"
        assert questions[q1.pk].duree_s == 90
        assert questions[q1.pk].choices.count() == 2
        assert questions[q2.pk].uid == "Q2"
        assert questions[q3.pk].uid == f"Q1-{quiz2.pk}"
        assert questions[q3.pk].duree_s == 120
        assert questions[q3.pk].type == "multiple"

        assert QuizV3.objects.get(pk=quiz1.pk).duree_s == 90
        assert QuizV3.objects.get(pk=quiz2.pk).duree_s == 120

        assert list(
            QuizQuestion.objects.filter(quiz_id=quiz1.pk)
            .order_by("position")
            .values_list("position", "question_id")
        ) == [(1, q1.pk), (2, q2.pk)]
        assert list(
            QuizQuestion.objects.filter(quiz_id=quiz2.pk)
            .order_by("position")
            .values_list("position", "question_id")
        ) == [(1, q3.pk)]
    finally:
        executeur = _executeur()
        executeur.migrate(executeur.loader.graph.leaf_nodes())

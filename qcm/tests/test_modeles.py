"""Invariants du modèle de données (AGENTS.md §3)."""

import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from qcm.import_questions import importer_quiz
from qcm.models import Answer, Participant
from qcm.tests.helpers import creer_session, donnees_quiz

pytestmark = pytest.mark.django_db


def test_code_session_genere_lisible_et_unique(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    codes = set()
    alphabet = set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")

    for _ in range(30):
        session = creer_session(quiz)
        assert len(session.code_session) == 6
        assert set(session.code_session) <= alphabet
        codes.add(session.code_session)

    assert len(codes) == 30


def test_sqlite_est_en_mode_wal():
    with connection.cursor() as curseur:
        curseur.execute("PRAGMA journal_mode;")
        assert curseur.fetchone()[0].lower() == "wal"


def test_participant_couleur_graine_et_symbole_persistes(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    participant = Participant.objects.create(session=session)

    recharge = Participant.objects.get(pk=participant.pk)
    assert recharge.couleur_assignee in (1, 2, 3, 4)
    assert recharge.graine_melange == participant.graine_melange
    assert recharge.symbole in ("●", "▲", "■", "◆")
    assert recharge.jeton_appareil == participant.jeton_appareil


def test_une_seule_reponse_par_participant_et_question(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    question = quiz.questions.get(uid="E1Q1")
    participant = Participant.objects.create(session=session)
    Answer.objects.create(
        session=session,
        participant=participant,
        question=question,
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Answer.objects.create(
            session=session,
            participant=participant,
            question=question,
            choix_selectionnes=["B"],
            id_client=uuid.uuid4(),
        )


def test_id_client_unique_globalement(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 2), proprietaire)
    session = creer_session(quiz)
    questions = list(quiz.questions.order_by("ordre"))
    premier = Participant.objects.create(session=session)
    second = Participant.objects.create(session=session)
    id_client = uuid.uuid4()
    Answer.objects.create(
        session=session,
        participant=premier,
        question=questions[0],
        choix_selectionnes=["A"],
        id_client=id_client,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Answer.objects.create(
            session=session,
            participant=second,
            question=questions[1],
            choix_selectionnes=["A"],
            id_client=id_client,
        )


def test_reponse_recoit_sa_session_automatiquement(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    question = quiz.questions.get(uid="E1Q1")
    participant = Participant.objects.create(session=session)

    reponse = Answer.objects.create(
        participant=participant,
        question=question,
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )

    assert reponse.session_id == session.pk
    assert reponse.source == Answer.SOURCE_APP
    assert reponse.recu_a is not None

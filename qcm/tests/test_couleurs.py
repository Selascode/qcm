"""Quatre couleurs, distribution des élèves et ordre des boutons."""

import pytest

from qcm.couleurs import COULEURS, NB_COULEURS
from qcm.import_json import importer_quiz
from qcm.models import Participant, Session
from qcm.services import lettres_melangees, question_courante_pour
from qcm.tests.helpers import creer_session, demarrer, donnees_quiz

pytestmark = pytest.mark.django_db


def test_palette_de_quatre_couleurs_et_symboles_distincts():
    assert NB_COULEURS == 4
    assert len({couleur["hex"] for couleur in COULEURS.values()}) == 4
    assert len({couleur["symbole"] for couleur in COULEURS.values()}) == 4


def test_quatre_questions_chaque_couleur_sur_sa_colonne(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 4), proprietaire)
    session = demarrer(creer_session(quiz))
    participants = [
        Participant.objects.create(session=session, couleur_assignee=couleur)
        for couleur in (1, 2, 3, 4)
    ]

    uids = [question_courante_pour(session, p).uid for p in participants]

    assert uids == ["E1Q1", "E1Q2", "E1Q3", "E1Q4"]


def test_deux_questions_replient_les_couleurs(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 2), proprietaire)
    session = demarrer(creer_session(quiz))
    participants = [
        Participant.objects.create(session=session, couleur_assignee=couleur)
        for couleur in (1, 2, 3, 4)
    ]

    uids = [question_courante_pour(session, p).uid for p in participants]

    assert uids == ["E1Q1", "E1Q2", "E1Q1", "E1Q2"]


def test_une_seule_question_tous_les_eleves_repondent(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = demarrer(creer_session(quiz))
    participants = [
        Participant.objects.create(session=session, couleur_assignee=couleur)
        for couleur in (1, 2, 3, 4)
    ]

    uids = {question_courante_pour(session, p).uid for p in participants}

    assert uids == {"E1Q1"}


def test_rotation_par_etape_dans_le_paquet(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 8), proprietaire)
    session = demarrer(creer_session(quiz))
    participant = Participant.objects.create(session=session, couleur_assignee=1)

    assert question_courante_pour(session, participant).uid == "E1Q1"

    for etape, uid in ((2, "E1Q2"), (4, "E1Q4"), (5, "E1Q5"), (8, "E1Q8")):
        Session.objects.filter(pk=session.pk).update(etape_courante=etape)
        session.refresh_from_db()
        assert question_courante_pour(session, participant).uid == uid


def test_ordre_des_lettres_deterministe_et_melange(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = demarrer(creer_session(quiz))
    question = quiz.questions.get(uid="E1Q1")
    participant = Participant.objects.create(session=session, graine_melange=42)

    premier = lettres_melangees(participant, question)
    second = lettres_melangees(participant, question)

    assert premier == second
    assert sorted(premier) == ["A", "B", "C"]

    ordres = {
        tuple(lettres_melangees(Participant(graine_melange=graine), question))
        for graine in range(20)
    }
    assert len(ordres) > 1

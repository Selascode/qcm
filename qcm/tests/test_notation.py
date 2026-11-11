"""Barème : fonctions pures ``note_question`` et ``note_seance`` (AGENTS.md §4)."""

import pytest

from qcm.models import Choice, Question, QuestionSet
from qcm.notation import note_question, note_seance

pytestmark = pytest.mark.django_db


def _question(proprietaire, corrects, nb_choix=3, type_="multiple"):
    question_set = QuestionSet.objects.create(
        nom="Barème", proprietaire=proprietaire
    )
    question = Question.objects.create(
        set=question_set,
        uid="Q1",
        enonce="Énoncé",
        type=type_,
        duree_s=60,
    )
    for index in range(nb_choix):
        Choice.objects.create(
            question=question,
            lettre="ABCDEF"[index],
            texte=f"Choix {index}",
            est_correct=index in corrects,
            position=index,
        )
    return question


def test_une_bonne_une_cochee(proprietaire):
    question = _question(proprietaire, {0})
    assert note_question(["A"], question) == pytest.approx(1.0)


def test_deux_bonnes_une_cochee(proprietaire):
    question = _question(proprietaire, {0, 1})
    assert note_question(["A"], question) == pytest.approx(0.5)


def test_deux_bonnes_une_bonne_et_une_mauvaise_penalite_active(proprietaire):
    question = _question(proprietaire, {0, 1})
    assert note_question(["A", "C"], question) == pytest.approx(0.0)


def test_deux_bonnes_une_bonne_et_une_mauvaise_penalite_desactivee(proprietaire):
    question = _question(proprietaire, {0, 1})
    assert note_question(
        ["A", "C"], question, penalite_active=False
    ) == pytest.approx(0.5)


def test_deux_bonnes_deux_bonnes(proprietaire):
    question = _question(proprietaire, {0, 1})
    assert note_question(["A", "B"], question) == pytest.approx(1.0)


def test_aucune_reponse(proprietaire):
    question = _question(proprietaire, {0, 1})
    assert note_question([], question) == pytest.approx(0.0)


def test_une_bonne_une_mauvaise_donne_moins_un(proprietaire):
    question = _question(proprietaire, {0})
    assert note_question(["B"], question) == pytest.approx(-1.0)


def test_note_bornee_au_facteur_de_penalite(proprietaire):
    question = _question(proprietaire, {0}, nb_choix=4)
    # 1 bonne réponse, 3 mauvaises cochées, facteur 1 : -3 ramené à -1.
    assert note_question(["B", "C", "D"], question) == pytest.approx(-1.0)
    assert note_question(
        ["B", "C", "D"], question, facteur_penalite=2.0
    ) == pytest.approx(-2.0)


def test_facteur_de_penalite_fractionnaire(proprietaire):
    question = _question(proprietaire, {0})
    assert note_question(
        ["B"], question, facteur_penalite=0.5
    ) == pytest.approx(-0.5)


def test_question_sans_bonne_reponse_ne_divise_pas_par_zero(proprietaire):
    question = _question(proprietaire, set())
    assert note_question(["A"], question) == pytest.approx(0.0)


def test_facteur_invalide_refuse(proprietaire):
    question = _question(proprietaire, {0})
    with pytest.raises(ValueError):
        note_question(["A"], question, facteur_penalite=0)


def test_les_lettres_inconnues_sont_ignorees(proprietaire):
    question = _question(proprietaire, {0})
    assert note_question(["A", "Z"], question) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("notes", "attendu"),
    [
        ([0.5, 1.0], 1.5),
        ([0.0], 0.0),
        ([], 0.0),
        ([-0.5, -1.0], 0.0),
        ([2.0, -1.0], 1.0),
    ],
)
def test_note_seance(notes, attendu):
    assert note_seance(notes) == pytest.approx(attendu)

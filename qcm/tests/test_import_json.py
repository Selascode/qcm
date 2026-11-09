"""Import JSON : cas nominal, format du fichier de démo et erreurs claires."""

import copy
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from qcm.import_json import ErreurImport, charger_fichier, importer_quiz
from qcm.models import Question, Quiz, Step

pytestmark = pytest.mark.django_db

RACINE = Path(__file__).resolve().parents[2]


def donnees_valides() -> dict:
    return {
        "titre": "Quiz test",
        "questions": [
            {
                "uid": "Q1",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Énoncé 1",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "Bonne", "correct": True},
                    {"lettre": "B", "texte": "Mauvaise", "correct": False},
                ],
            },
            {
                "uid": "Q2",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Énoncé 2",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "Bonne", "correct": True},
                    {"lettre": "B", "texte": "Mauvaise", "correct": False},
                ],
            },
            {
                "uid": "Q3",
                "etape": 2,
                "duree_s": 30,
                "enonce": "Énoncé 3",
                "type": "multiple",
                "afficher_indice_multiple": True,
                "choix": [
                    {"lettre": "A", "texte": "Bonne A", "correct": True},
                    {"lettre": "B", "texte": "Bonne B", "correct": True},
                    {"lettre": "C", "texte": "Mauvaise", "correct": False},
                ],
            },
        ],
    }


def erreurs(donnees, proprietaire) -> str:
    with pytest.raises(ErreurImport) as exc:
        importer_quiz(donnees, proprietaire)
    return " ".join(exc.value.messages)


def test_import_valide(proprietaire):
    quiz = importer_quiz(donnees_valides(), proprietaire)

    assert quiz.titre == "Quiz test"
    assert quiz.proprietaire == proprietaire
    assert list(quiz.steps.values_list("numero", "duree_s")) == [(1, 60), (2, 30)]

    questions = list(
        quiz.questions.order_by("step__numero", "ordre").values(
            "uid", "step__numero", "ordre", "couleur_slot"
        )
    )
    assert questions == [
        {"uid": "Q1", "step__numero": 1, "ordre": 1, "couleur_slot": 1},
        {"uid": "Q2", "step__numero": 1, "ordre": 2, "couleur_slot": 2},
        {"uid": "Q3", "step__numero": 2, "ordre": 1, "couleur_slot": 1},
    ]

    q3 = Question.objects.get(quiz=quiz, uid="Q3")
    assert q3.type == "multiple"
    assert q3.afficher_indice_multiple is True
    assert list(
        q3.choices.order_by("position").values_list("lettre", "texte", "est_correct")
    ) == [
        ("A", "Bonne A", True),
        ("B", "Bonne B", True),
        ("C", "Mauvaise", False),
    ]


def test_import_du_fichier_de_demo(proprietaire):
    donnees = charger_fichier(RACINE / "examples" / "quiz_demo.json")
    quiz = importer_quiz(donnees, proprietaire)

    assert quiz.steps.count() == 5
    assert quiz.questions.count() == 10
    assert list(quiz.steps.values_list("numero", "duree_s")) == [
        (1, 90),
        (2, 60),
        (3, 120),
        (4, 60),
        (5, 90),
    ]
    assert quiz.questions.filter(couleur_slot=4).count() == 1


def test_import_est_transactionnel(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][1]["uid"] = "Q1"

    message = erreurs(donnees, proprietaire)

    assert "dupliqué" in message
    assert Quiz.objects.count() == 0


def test_titre_manquant(proprietaire):
    donnees = donnees_valides()
    del donnees["titre"]

    assert "titre" in erreurs(donnees, proprietaire)


def test_liste_de_questions_vide(proprietaire):
    donnees = donnees_valides()
    donnees["questions"] = []

    assert "questions" in erreurs(donnees, proprietaire)


def test_questions_pas_un_objet(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0] = "pas un objet"

    assert "doit être un objet" in erreurs(donnees, proprietaire)


def test_etapes_avec_trou(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][2]["etape"] = 3

    assert "1 à N" in erreurs(donnees, proprietaire)


def test_maximum_quatre_questions_par_etape(proprietaire):
    donnees = donnees_valides()
    for index in range(3, 6):
        question = copy.deepcopy(donnees["questions"][0])
        question["uid"] = f"Q{index + 1}"
        donnees["questions"].append(question)

    assert "maximum 4" in erreurs(donnees, proprietaire)


def test_durees_differentes_dans_une_etape(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][1]["duree_s"] = 61

    assert "durées différentes" in erreurs(donnees, proprietaire)


def test_question_unique_avec_deux_bonnes_reponses(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][1]["correct"] = True

    assert "exactement une bonne réponse" in erreurs(donnees, proprietaire)


def test_question_unique_sans_bonne_reponse(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][0]["correct"] = False

    assert "exactement une bonne réponse" in erreurs(donnees, proprietaire)


def test_question_multiple_sans_bonne_reponse(proprietaire):
    donnees = donnees_valides()
    for choix in donnees["questions"][2]["choix"]:
        choix["correct"] = False

    assert "au moins une bonne réponse" in erreurs(donnees, proprietaire)


@pytest.mark.parametrize("nombre", [1, 7])
def test_nombre_de_choix_hors_bornes(proprietaire, nombre):
    donnees = donnees_valides()
    choix = donnees["questions"][0]["choix"]
    while len(choix) < nombre:
        choix.append(
            {
                "lettre": "C",
                "texte": "Autre",
                "correct": False,
            }
        )
    donnees["questions"][0]["choix"] = choix[:nombre]

    assert "2 à 6" in erreurs(donnees, proprietaire)


def test_lettres_dupliquees(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][1]["lettre"] = "A"

    assert "dupliquée" in erreurs(donnees, proprietaire)


def test_lettre_invalide(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][0]["lettre"] = "Z"

    assert "entre A et F" in erreurs(donnees, proprietaire)


def test_type_invalide(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["type"] = "libre"

    assert "type" in erreurs(donnees, proprietaire)


def test_etape_et_duree_invalides(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][0]["etape"] = 0
    donnees["questions"][0]["duree_s"] = 0

    message = erreurs(donnees, proprietaire)
    assert "etape" in message
    assert "duree_s" in message


def test_afficher_indice_multiple_non_booleen(proprietaire):
    donnees = donnees_valides()
    donnees["questions"][2]["afficher_indice_multiple"] = "oui"

    assert "booléen" in erreurs(donnees, proprietaire)


def test_correct_manquant(proprietaire):
    donnees = donnees_valides()
    del donnees["questions"][0]["choix"][1]["correct"]

    assert "correct" in erreurs(donnees, proprietaire)


def test_json_invalide(tmp_path):
    chemin = tmp_path / "invalide.json"
    chemin.write_text("{", encoding="utf-8")

    with pytest.raises(ErreurImport) as exc:
        charger_fichier(chemin)
    assert "JSON invalide" in str(exc.value)


def test_commande_import(proprietaire, tmp_path):
    chemin = tmp_path / "quiz.json"
    chemin.write_text(json.dumps(donnees_valides()), encoding="utf-8")
    sortie = StringIO()

    call_command(
        "import_quiz",
        chemin,
        "--proprietaire",
        proprietaire.username,
        stdout=sortie,
    )

    assert "QCM importé" in sortie.getvalue()
    assert Quiz.objects.filter(titre="Quiz test").exists()


def test_commande_import_utilisateur_inconnu(proprietaire, tmp_path):
    chemin = tmp_path / "quiz.json"
    chemin.write_text(json.dumps(donnees_valides()), encoding="utf-8")

    with pytest.raises(CommandError):
        call_command(
            "import_quiz",
            chemin,
            "--proprietaire",
            "inconnu",
        )


def test_commande_import_erreur_affiche_les_messages(proprietaire, tmp_path):
    donnees = donnees_valides()
    donnees["titre"] = ""
    chemin = tmp_path / "quiz.json"
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    erreur = StringIO()

    with pytest.raises(CommandError):
        call_command(
            "import_quiz",
            chemin,
            "--proprietaire",
            proprietaire.username,
            stderr=erreur,
        )

    assert "titre" in erreur.getvalue()


def test_question_uid_unique_par_quiz(proprietaire):
    quiz = importer_quiz(donnees_valides(), proprietaire)
    autre_etape = Step.objects.create(quiz=quiz, numero=3, duree_s=20)
    question = Question(
        quiz=quiz,
        step=autre_etape,
        uid="Q1",
        enonce="Doublon",
        type="unique",
        ordre=1,
        couleur_slot=1,
    )

    with pytest.raises(ValidationError) as exc:
        question.full_clean()
    assert "existe déjà" in str(exc.value)


def test_question_maximum_quatre_par_etape(proprietaire):
    quiz = importer_quiz(donnees_valides(), proprietaire)
    etape = quiz.steps.get(numero=2)
    for index in range(4):
        Question.objects.create(
            quiz=quiz,
            step=etape,
            uid=f"EXTRA{index}",
            enonce="Extra",
            type="unique",
            ordre=index + 1,
            couleur_slot=(index % 4) + 1,
        )
    question = Question(
        quiz=quiz,
        step=etape,
        uid="TROP",
        enonce="Trop",
        type="unique",
        ordre=5,
        couleur_slot=1,
    )

    with pytest.raises(ValidationError) as exc:
        question.full_clean()
    assert "plus de 4 questions" in str(exc.value)

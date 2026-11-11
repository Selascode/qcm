"""Import JSON/CSV de questions dans la banque (V3)."""

import csv
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError

from qcm.import_questions import (
    ErreurImport,
    charger_fichier_csv,
    charger_fichier_json,
    charger_fichier_questions,
    importer_questions,
    importer_quiz,
)
from qcm.models import Question, QuestionSet, Quiz

pytestmark = pytest.mark.django_db

RACINE = Path(__file__).resolve().parents[2]


def donnees_valides() -> dict:
    return {
        "titre": "Ensemble test",
        "questions": [
            {
                "uid": "Q1",
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
                "duree_s": 120,
                "enonce": "Énoncé 2",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "Bonne", "correct": True},
                    {"lettre": "B", "texte": "Mauvaise", "correct": False},
                ],
            },
            {
                "uid": "Q3",
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


@pytest.fixture
def question_set(proprietaire):
    return QuestionSet.objects.create(nom="CM 3", proprietaire=proprietaire)


def erreurs(donnees, question_set) -> str:
    with pytest.raises(ErreurImport) as exc:
        importer_questions(donnees, question_set)
    return " ".join(exc.value.messages)


def test_import_json_dans_un_ensemble(question_set):
    questions = importer_questions(donnees_valides(), question_set)

    assert len(questions) == 3
    assert list(
        Question.objects.filter(set=question_set).values_list("uid", "ordre")
    ) == [("Q1", 1), ("Q2", 2), ("Q3", 3)]
    assert list(
        Question.objects.filter(set=question_set).values_list("uid", "duree_s")
    ) == [("Q1", 60), ("Q2", 120), ("Q3", 30)]

    q3 = Question.objects.get(set=question_set, uid="Q3")
    assert q3.type == "multiple"
    assert q3.afficher_indice_multiple is True
    assert list(
        q3.choices.order_by("position").values_list(
            "lettre", "texte", "est_correct"
        )
    ) == [
        ("A", "Bonne A", True),
        ("B", "Bonne B", True),
        ("C", "Mauvaise", False),
    ]


def test_import_ajoute_a_la_suite_de_l_ensemble(question_set):
    importer_questions(donnees_valides(), question_set)
    donnees = {
        "questions": [
            {
                "uid": "Q4",
                "enonce": "Énoncé 4",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "Bonne", "correct": True},
                    {"lettre": "B", "texte": "Mauvaise", "correct": False},
                ],
            }
        ]
    }

    importer_questions(donnees, question_set)

    assert Question.objects.get(set=question_set, uid="Q4").ordre == 4


def test_racine_liste_acceptee(question_set):
    donnees = donnees_valides()["questions"]

    importer_questions(donnees, question_set)

    assert question_set.questions.count() == 3


def test_etape_et_titre_ignores(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["etape"] = 4
    donnees["questions"][2]["etape"] = 1

    importer_questions(donnees, question_set)

    assert list(
        question_set.questions.order_by("ordre").values_list("uid", flat=True)
    ) == ["Q1", "Q2", "Q3"]


def test_import_quiz_historique(proprietaire):
    quiz = importer_quiz(donnees_valides(), proprietaire)

    assert quiz.titre == "Ensemble test"
    assert quiz.proprietaire == proprietaire
    assert quiz.duree_s == 120
    assert list(
        quiz.quiz_questions.order_by("position").values_list(
            "position", "question__uid"
        )
    ) == [(1, "Q1"), (2, "Q2"), (3, "Q3")]
    assert (
        QuestionSet.objects.get(proprietaire=proprietaire).nom
        == "Ensemble test"
    )


def test_import_du_fichier_de_demo(question_set):
    donnees = charger_fichier_json(RACINE / "examples" / "quiz_demo.json")
    questions = importer_questions(donnees, question_set)

    assert len(questions) == 10
    assert questions[0].uid == "Q1"
    assert questions[0].duree_s == 90
    assert question_set.questions.count() == 10


def test_import_est_transactionnel(question_set):
    donnees = donnees_valides()
    donnees["questions"][1]["uid"] = "Q1"

    message = erreurs(donnees, question_set)

    assert "existe déjà" in message
    assert Question.objects.count() == 0


def test_uid_deja_present_dans_l_ensemble(question_set):
    Question.objects.create(
        set=question_set,
        uid="Q1",
        enonce="Déjà là",
        type="unique",
    )

    message = erreurs(donnees_valides(), question_set)

    assert "existe déjà" in message
    assert question_set.questions.count() == 1


def test_liste_de_questions_vide(question_set):
    assert "questions" in erreurs({"questions": []}, question_set)


def test_document_sans_questions(question_set):
    assert "questions" in erreurs({"titre": "Vide"}, question_set)


def test_questions_pas_un_objet(question_set):
    donnees = donnees_valides()
    donnees["questions"][0] = "pas un objet"

    assert "doit être un objet" in erreurs(donnees, question_set)


def test_question_unique_avec_deux_bonnes_reponses(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][1]["correct"] = True

    assert "exactement une bonne réponse" in erreurs(donnees, question_set)


def test_question_unique_sans_bonne_reponse(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][0]["correct"] = False

    assert "exactement une bonne réponse" in erreurs(donnees, question_set)


def test_question_multiple_sans_bonne_reponse(question_set):
    donnees = donnees_valides()
    for choix in donnees["questions"][2]["choix"]:
        choix["correct"] = False

    assert "au moins une bonne réponse" in erreurs(donnees, question_set)


@pytest.mark.parametrize("nombre", [1, 7])
def test_nombre_de_choix_hors_bornes(question_set, nombre):
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

    assert "2 à 6" in erreurs(donnees, question_set)


def test_lettres_dupliquees(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][1]["lettre"] = "A"

    assert "dupliquée" in erreurs(donnees, question_set)


def test_lettre_invalide(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["choix"][0]["lettre"] = "Z"

    assert "entre A et F" in erreurs(donnees, question_set)


def test_type_invalide(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["type"] = "libre"

    assert "type" in erreurs(donnees, question_set)


def test_duree_invalide(question_set):
    donnees = donnees_valides()
    donnees["questions"][0]["duree_s"] = 0

    assert "duree_s" in erreurs(donnees, question_set)


def test_afficher_indice_multiple_non_booleen(question_set):
    donnees = donnees_valides()
    donnees["questions"][2]["afficher_indice_multiple"] = "oui"

    assert "booléen" in erreurs(donnees, question_set)


def test_correct_manquant(question_set):
    donnees = donnees_valides()
    del donnees["questions"][0]["choix"][1]["correct"]

    assert "correct" in erreurs(donnees, question_set)


def test_json_invalide(tmp_path):
    chemin = tmp_path / "invalide.json"
    chemin.write_text("{", encoding="utf-8")

    with pytest.raises(ErreurImport) as exc:
        charger_fichier_json(chemin)
    assert "JSON invalide" in str(exc.value)


def _ecrire_csv(chemin: Path, lignes: list[dict], colonnes: list[str]) -> None:
    with open(chemin, "w", encoding="utf-8", newline="") as fichier:
        redacteur = csv.DictWriter(fichier, fieldnames=colonnes)
        redacteur.writeheader()
        redacteur.writerows(lignes)


def test_import_csv_regroupe_les_choix(tmp_path, question_set):
    chemin = tmp_path / "questions.csv"
    _ecrire_csv(
        chemin,
        [
            {
                "uid": "Q1",
                "enonce": "Énoncé CSV",
                "type": "unique",
                "lettre": "A",
                "texte": "Bonne",
                "correct": "oui",
                "duree_s": "90",
            },
            {
                "uid": "Q1",
                "enonce": "",
                "type": "",
                "lettre": "B",
                "texte": "Mauvaise",
                "correct": "non",
                "duree_s": "",
            },
            {
                "uid": "Q2",
                "enonce": "Deuxième",
                "type": "multiple",
                "lettre": "A",
                "texte": "Bonne A",
                "correct": "1",
                "duree_s": "30",
            },
            {
                "uid": "Q2",
                "enonce": "",
                "type": "",
                "lettre": "B",
                "texte": "Bonne B",
                "correct": "vrai",
                "duree_s": "",
            },
        ],
        ["uid", "enonce", "type", "lettre", "texte", "correct", "duree_s"],
    )

    questions = importer_questions(charger_fichier_csv(chemin), question_set)

    assert [question.uid for question in questions] == ["Q1", "Q2"]
    assert questions[0].duree_s == 90
    assert questions[0].choices.count() == 2
    assert questions[1].type == "multiple"
    assert questions[1].choices.filter(est_correct=True).count() == 2


def test_charger_fichier_questions_selon_extension(tmp_path, question_set):
    chemin = tmp_path / "questions.csv"
    _ecrire_csv(
        chemin,
        [
            {
                "uid": "Q1",
                "enonce": "Énoncé",
                "type": "unique",
                "lettre": "A",
                "texte": "Bonne",
                "correct": "oui",
            },
            {
                "uid": "Q1",
                "enonce": "",
                "type": "",
                "lettre": "B",
                "texte": "Mauvaise",
                "correct": "non",
            },
        ],
        ["uid", "enonce", "type", "lettre", "texte", "correct"],
    )

    importer_questions(charger_fichier_questions(chemin), question_set)

    assert question_set.questions.count() == 1


def test_csv_colonnes_manquantes(tmp_path):
    chemin = tmp_path / "questions.csv"
    chemin.write_text("uid,enonce\nQ1,Énoncé\n", encoding="utf-8")

    with pytest.raises(ErreurImport) as exc:
        charger_fichier_csv(chemin)
    assert "Colonnes CSV manquantes" in str(exc.value)


def test_csv_booleen_invalide(tmp_path):
    chemin = tmp_path / "questions.csv"
    _ecrire_csv(
        chemin,
        [
            {
                "uid": "Q1",
                "enonce": "Énoncé",
                "type": "unique",
                "lettre": "A",
                "texte": "Bonne",
                "correct": "peut-être",
            },
        ],
        ["uid", "enonce", "type", "lettre", "texte", "correct"],
    )

    with pytest.raises(ErreurImport) as exc:
        charger_fichier_csv(chemin)
    assert "booléen" in str(exc.value)


def test_question_uid_unique_par_set(proprietaire, question_set):
    Question.objects.create(
        set=question_set,
        uid="Q1",
        enonce="Déjà là",
        type="unique",
    )
    doublon = Question(
        set=question_set,
        uid="Q1",
        enonce="Doublon",
        type="unique",
    )
    with pytest.raises(ValidationError) as exc:
        doublon.full_clean()
    assert "existe déjà" in str(exc.value)

    autre_set = QuestionSet.objects.create(
        nom="Autre ensemble", proprietaire=proprietaire
    )
    Question.objects.create(
        set=autre_set,
        uid="Q1",
        enonce="Même uid, autre ensemble",
        type="unique",
    )
    assert Question.objects.filter(uid="Q1").count() == 2


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
    assert Quiz.objects.filter(titre="Ensemble test").exists()
    assert QuestionSet.objects.filter(nom="Ensemble test").exists()


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
    donnees["questions"][0]["uid"] = ""
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

    assert "uid" in erreur.getvalue()


def test_import_web(proprietaire, question_set, client):
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile(
        "questions.json",
        json.dumps(donnees_valides()).encode("utf-8"),
        content_type="application/json",
    )

    reponse = client.post(
        f"/ensemble/{question_set.pk}/importer-questions/",
        {"fichier": fichier, "set": str(question_set.pk)},
    )

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "3 question(s) importée(s)" in contenu
    assert question_set.questions.count() == 3


def test_import_web_choisit_l_ensemble_de_destination(
    proprietaire, question_set, client
):
    autre_set = QuestionSet.objects.create(
        nom="Autre", proprietaire=proprietaire
    )
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile(
        "questions.json",
        json.dumps(donnees_valides()).encode("utf-8"),
        content_type="application/json",
    )

    reponse = client.post(
        f"/ensemble/{question_set.pk}/importer-questions/",
        {"fichier": fichier, "set": str(autre_set.pk)},
    )

    assert reponse.status_code == 200
    assert autre_set.questions.count() == 3
    assert question_set.questions.count() == 0


def test_import_web_autre_proprietaire_refuse(
    proprietaire, autre_proprietaire, question_set, client
):
    client.force_login(autre_proprietaire)

    reponse = client.get(f"/ensemble/{question_set.pk}/importer-questions/")

    assert reponse.status_code == 404


def test_import_web_format_refuse(proprietaire, question_set, client):
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile(
        "questions.txt", b"n'importe quoi", content_type="text/plain"
    )

    reponse = client.post(
        f"/ensemble/{question_set.pk}/importer-questions/",
        {"fichier": fichier, "set": str(question_set.pk)},
    )

    assert reponse.status_code == 200
    assert "Format non reconnu" in reponse.content.decode()
    assert question_set.questions.count() == 0

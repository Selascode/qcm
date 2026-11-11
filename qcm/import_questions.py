"""Import de questions (JSON/CSV) dans la banque de questions.

Format JSON V3 (le champ ``titre`` et l'ancien ``etape`` sont ignorés) ::

    {
      "questions": [
        {
          "uid": "Q1",
          "enonce": "…",
          "type": "unique",
          "duree_s": 60,
          "choix": [
            {"lettre": "A", "texte": "…", "correct": false},
            {"lettre": "B", "texte": "…", "correct": true}
          ]
        }
      ]
    }

La racine peut aussi être directement une liste de questions. Format CSV :
une ligne par choix, avec l'en-tête
``uid,enonce,type,lettre,texte,correct[,duree_s][,afficher_indice_multiple]``.
``enonce``, ``type`` et ``duree_s`` sont lus sur la première ligne de chaque
``uid``.

L'import est transactionnel : en cas d'erreur, aucune question n'est créée.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from qcm.models import Choice, Question, QuestionSet, Quiz, QuizQuestion

DUREE_PAR_DEFAUT = 60
COLONNES_CSV_OBLIGATOIRES = ("uid", "enonce", "type", "lettre", "texte", "correct")


class ErreurImport(ValueError):
    """Erreur de format ou de contenu du fichier importé."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        super().__init__(" ".join(self.messages))


@dataclass
class _QuestionNormalisee:
    uid: str
    enonce: str
    type: str
    afficher_indice_multiple: bool
    choix: list[dict] = field(default_factory=list)
    duree_s: int = DUREE_PAR_DEFAUT


def _est_entier(valeur) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _questions_du_document(donnees) -> list:
    if isinstance(donnees, list):
        return donnees
    if not isinstance(donnees, dict):
        raise ErreurImport(
            "Le fichier doit contenir un objet JSON avec « questions » ou une "
            "liste de questions."
        )
    questions = donnees.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ErreurImport("`questions` doit être une liste non vide.")
    return questions


def _normaliser_questions(
    questions_brutes,
    identifiants_existants=(),
) -> list[_QuestionNormalisee]:
    erreurs: list[str] = []
    normalisees: list[_QuestionNormalisee] = []
    identifiants: set[str] = set(identifiants_existants)

    for index, brute in enumerate(questions_brutes, start=1):
        prefixe = f"questions[{index}]"
        if not isinstance(brute, dict):
            erreurs.append(f"{prefixe} doit être un objet.")
            continue

        uid = brute.get("uid")
        if not isinstance(uid, str) or not uid.strip():
            erreurs.append(f"{prefixe}.uid doit être une chaîne non vide.")
            uid = ""
        elif len(uid) > 64:
            erreurs.append(f"{prefixe}.uid dépasse 64 caractères.")
        if uid:
            if uid in identifiants:
                erreurs.append(
                    f"{prefixe}.uid « {uid} » existe déjà dans cet ensemble."
                )
            identifiants.add(uid)

        enonce = brute.get("enonce")
        if not isinstance(enonce, str) or not enonce.strip():
            erreurs.append(f"{prefixe}.enonce doit être une chaîne non vide.")
            enonce = ""

        type_question = brute.get("type")
        if type_question not in (Question.TYPE_UNIQUE, Question.TYPE_MULTIPLE):
            erreurs.append(
                f'{prefixe}.type doit valoir "{Question.TYPE_UNIQUE}" '
                f'ou "{Question.TYPE_MULTIPLE}".'
            )

        duree_s = brute.get("duree_s", DUREE_PAR_DEFAUT)
        if not _est_entier(duree_s) or duree_s < 1:
            erreurs.append(f"{prefixe}.duree_s doit être un entier > 0.")
            duree_s = DUREE_PAR_DEFAUT

        afficher = brute.get("afficher_indice_multiple", False)
        if not isinstance(afficher, bool):
            erreurs.append(
                f"{prefixe}.afficher_indice_multiple doit être un booléen."
            )
            afficher = False

        choix_bruts = brute.get("choix")
        choix: list[dict] = []
        if not isinstance(choix_bruts, list) or not 2 <= len(choix_bruts) <= 6:
            erreurs.append(f"{prefixe}.choix doit être une liste de 2 à 6 choix.")
            choix_bruts = []

        lettres: set[str] = set()
        for position, choix_brut in enumerate(choix_bruts, start=1):
            prefixe_choix = f"{prefixe}.choix[{position}]"
            if not isinstance(choix_brut, dict):
                erreurs.append(f"{prefixe_choix} doit être un objet.")
                continue

            lettre = choix_brut.get("lettre")
            if (
                not isinstance(lettre, str)
                or len(lettre) != 1
                or lettre not in "ABCDEF"
            ):
                erreurs.append(
                    f"{prefixe_choix}.lettre doit être une lettre entre A et F."
                )
                lettre = ""
            elif lettre in lettres:
                erreurs.append(
                    f"{prefixe_choix}.lettre « {lettre} » est dupliquée."
                )
            else:
                lettres.add(lettre)

            texte = choix_brut.get("texte")
            if not isinstance(texte, str) or not texte.strip():
                erreurs.append(
                    f"{prefixe_choix}.texte doit être une chaîne non vide."
                )
                texte = ""

            correct = choix_brut.get("correct")
            if not isinstance(correct, bool):
                erreurs.append(f"{prefixe_choix}.correct doit être un booléen.")
                correct = False

            choix.append({"lettre": lettre, "texte": texte, "correct": correct})

        nombre_corrects = sum(1 for choix_possible in choix if choix_possible["correct"])
        if type_question == Question.TYPE_UNIQUE and nombre_corrects != 1:
            erreurs.append(
                f"{prefixe} : une question « unique » doit avoir exactement "
                "une bonne réponse."
            )
        if type_question == Question.TYPE_MULTIPLE and nombre_corrects < 1:
            erreurs.append(
                f"{prefixe} : une question « multiple » doit avoir au moins "
                "une bonne réponse."
            )

        normalisees.append(
            _QuestionNormalisee(
                uid=uid,
                enonce=enonce,
                type=type_question,
                afficher_indice_multiple=afficher,
                choix=choix,
                duree_s=duree_s,
            )
        )

    if erreurs:
        raise ErreurImport(erreurs)

    return normalisees


def valider_questions(
    donnees, identifiants_existants=()
) -> list[_QuestionNormalisee]:
    """Valide un document JSON/liste et retourne les questions normalisées."""
    return _normaliser_questions(
        _questions_du_document(donnees), identifiants_existants
    )


def importer_questions(donnees, question_set: QuestionSet) -> list[Question]:
    """Valide puis crée les questions dans ``question_set`` (tout ou rien)."""
    identifiants_existants = set(
        question_set.questions.values_list("uid", flat=True)
    )
    questions = _normaliser_questions(
        _questions_du_document(donnees), identifiants_existants
    )
    ordre_depart = (
        question_set.questions.aggregate(maximum=Max("ordre"))["maximum"] or 0
    )
    creees: list[Question] = []
    with transaction.atomic():
        for position, question_normalisee in enumerate(questions, start=1):
            question = Question(
                set=question_set,
                uid=question_normalisee.uid,
                enonce=question_normalisee.enonce,
                type=question_normalisee.type,
                afficher_indice_multiple=(
                    question_normalisee.afficher_indice_multiple
                ),
                ordre=ordre_depart + position,
                duree_s=question_normalisee.duree_s,
            )
            try:
                question.full_clean()
            except ValidationError as exc:
                raise ErreurImport(
                    f"Question {question_normalisee.uid} invalide : "
                    f"{exc.messages}"
                ) from exc
            question.save()
            Choice.objects.bulk_create(
                [
                    Choice(
                        question=question,
                        lettre=choix["lettre"],
                        texte=choix["texte"],
                        est_correct=choix["correct"],
                        position=position_choix,
                    )
                    for position_choix, choix in enumerate(
                        question_normalisee.choix, start=1
                    )
                ]
            )
            creees.append(question)
    return creees


def _nom_set_unique(proprietaire, base: str) -> str:
    nom = base
    numero = 2
    while QuestionSet.objects.filter(
        proprietaire=proprietaire, nom=nom
    ).exists():
        nom = f"{base} ({numero})"
        numero += 1
    return nom


def importer_quiz(donnees, proprietaire) -> Quiz:
    """Import historique d'un QCM : crée un ensemble puis sélectionne tout.

    Conservé pour la commande ``import_quiz`` et les fichiers V1/V2 : les
    questions vont dans un nouvel ensemble nommé d'après ``titre`` et le QCM
    les sélectionne toutes dans l'ordre du fichier.
    """
    if isinstance(donnees, dict):
        titre = donnees.get("titre")
    else:
        titre = None
    base = titre.strip() if isinstance(titre, str) and titre.strip() else "Import"
    with transaction.atomic():
        question_set = QuestionSet.objects.create(
            nom=_nom_set_unique(proprietaire, base),
            proprietaire=proprietaire,
        )
        questions = importer_questions(donnees, question_set)
        quiz = Quiz.objects.create(
            titre=question_set.nom,
            proprietaire=proprietaire,
            duree_s=max(
                [DUREE_PAR_DEFAUT, *(question.duree_s for question in questions)]
            ),
        )
        QuizQuestion.objects.bulk_create(
            [
                QuizQuestion(quiz=quiz, question=question, position=position)
                for position, question in enumerate(questions, start=1)
            ]
        )
        return quiz


def charger_fichier_json(chemin: Path):
    """Lit un fichier JSON en produisant une erreur lisible."""
    try:
        with open(chemin, encoding="utf-8") as fichier:
            return json.load(fichier)
    except OSError as exc:
        raise ErreurImport(f"Impossible de lire {chemin} : {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErreurImport(
            f"JSON invalide ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}"
        ) from exc


def _booleen_csv(valeur: str, prefixe: str, erreurs: list[str]):
    valeur_normalisee = (valeur or "").strip().lower()
    if valeur_normalisee in ("1", "true", "vrai", "oui", "x"):
        return True
    if valeur_normalisee in ("0", "false", "faux", "non", ""):
        return False
    erreurs.append(f"{prefixe} : « {valeur} » n'est pas un booléen (oui/non).")
    return False


def charger_fichier_csv(chemin: Path) -> list[dict]:
    """Lit un CSV « une ligne par choix » et regroupe les lignes par ``uid``."""
    try:
        with open(chemin, encoding="utf-8-sig", newline="") as fichier:
            lecteur = csv.DictReader(fichier)
            colonnes = set(lecteur.fieldnames or [])
            manquantes = [
                colonne
                for colonne in COLONNES_CSV_OBLIGATOIRES
                if colonne not in colonnes
            ]
            if manquantes:
                raise ErreurImport(
                    "Colonnes CSV manquantes : " + ", ".join(manquantes) + "."
                )
            erreurs: list[str] = []
            questions: dict[str, dict] = {}
            for numero_ligne, ligne in enumerate(lecteur, start=2):
                prefixe = f"ligne {numero_ligne}"
                uid = (ligne.get("uid") or "").strip()
                if not uid:
                    erreurs.append(f"{prefixe} : uid vide.")
                    continue
                if uid not in questions:
                    duree_brute = (ligne.get("duree_s") or "").strip()
                    duree_s = DUREE_PAR_DEFAUT
                    if duree_brute:
                        try:
                            duree_s = int(duree_brute)
                        except ValueError:
                            erreurs.append(
                                f"{prefixe} : duree_s doit être un entier > 0."
                            )
                    questions[uid] = {
                        "uid": uid,
                        "enonce": ligne.get("enonce") or "",
                        "type": (ligne.get("type") or "").strip(),
                        "duree_s": duree_s,
                        "afficher_indice_multiple": _booleen_csv(
                            ligne.get("afficher_indice_multiple") or "",
                            prefixe,
                            erreurs,
                        ),
                        "choix": [],
                    }
                questions[uid]["choix"].append(
                    {
                        "lettre": (ligne.get("lettre") or "").strip(),
                        "texte": ligne.get("texte") or "",
                        "correct": _booleen_csv(
                            ligne.get("correct") or "", prefixe, erreurs
                        ),
                    }
                )
    except OSError as exc:
        raise ErreurImport(f"Impossible de lire {chemin} : {exc}") from exc

    if erreurs:
        raise ErreurImport(erreurs)
    if not questions:
        raise ErreurImport("Le fichier CSV ne contient aucune question.")
    return list(questions.values())


def charger_fichier_questions(chemin: Path):
    """Charge un fichier .json ou .csv selon son extension."""
    suffixe = Path(chemin).suffix.lower()
    if suffixe == ".json":
        return charger_fichier_json(chemin)
    if suffixe == ".csv":
        return charger_fichier_csv(chemin)
    raise ErreurImport(
        "Format non reconnu : utilisez un fichier .json ou .csv."
    )

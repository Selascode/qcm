"""Import JSON d'un QCM (format SPEC §5, figé pour la V1).

Format accepté ::

    {
      "titre": "CM 3",
      "questions": [
        {
          "uid": "Q1",
          "etape": 1,
          "duree_s": 60,
          "enonce": "…",
          "type": "unique",
          "choix": [
            {"lettre": "A", "texte": "…", "correct": false},
            {"lettre": "B", "texte": "…", "correct": true}
          ]
        }
      ]
    }

La durée est portée par l'étape : toutes les questions d'une même ``etape``
doivent annoncer la même ``duree_s``. Les questions d'une étape reçoivent
``ordre`` et ``couleur_slot`` 1, 2, 3, 4 dans l'ordre du fichier.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from qcm.models import Choice, Question, Quiz, Step


class ErreurImport(ValueError):
    """Erreur de format ou de contenu du fichier JSON."""

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
    etape: int = 1
    duree_s: int = 1
    ordre: int = 1
    couleur_slot: int = 1


def _est_entier(valeur) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _normaliser(donnees) -> tuple[str, list[_QuestionNormalisee]]:
    erreurs: list[str] = []
    if not isinstance(donnees, dict):
        raise ErreurImport("Le fichier doit contenir un objet JSON.")

    titre = donnees.get("titre")
    if not isinstance(titre, str) or not titre.strip():
        erreurs.append("`titre` doit être une chaîne non vide.")
        titre = ""

    questions_brutes = donnees.get("questions")
    if not isinstance(questions_brutes, list) or not questions_brutes:
        erreurs.append("`questions` doit être une liste non vide.")
        questions_brutes = []

    normalisees: list[_QuestionNormalisee] = []
    uids: set[str] = set()
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
            if uid in uids:
                erreurs.append(f"{prefixe}.uid « {uid} » est dupliqué dans le QCM.")
            uids.add(uid)

        etape = brute.get("etape")
        if not _est_entier(etape) or etape < 1:
            erreurs.append(f"{prefixe}.etape doit être un entier >= 1.")

        duree_s = brute.get("duree_s")
        if not _est_entier(duree_s) or duree_s < 1:
            erreurs.append(f"{prefixe}.duree_s doit être un entier > 0.")

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

        afficher = brute.get("afficher_indice_multiple", False)
        if not isinstance(afficher, bool):
            erreurs.append(f"{prefixe}.afficher_indice_multiple doit être un booléen.")

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
                erreurs.append(f"{prefixe_choix}.lettre « {lettre} » est dupliquée.")
            else:
                lettres.add(lettre)

            texte = choix_brut.get("texte")
            if not isinstance(texte, str) or not texte.strip():
                erreurs.append(f"{prefixe_choix}.texte doit être une chaîne non vide.")
                texte = ""

            correct = choix_brut.get("correct")
            if not isinstance(correct, bool):
                erreurs.append(f"{prefixe_choix}.correct doit être un booléen.")

            choix.append({"lettre": lettre, "texte": texte, "correct": correct})

        nombre_corrects = sum(1 for c in choix if c["correct"] is True)
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
                etape=etape,
                duree_s=duree_s,
            )
        )

    if erreurs:
        raise ErreurImport(erreurs)

    par_etape: dict[int, list[_QuestionNormalisee]] = defaultdict(list)
    for question in normalisees:
        par_etape[question.etape].append(question)

    numeros = sorted(par_etape)
    if numeros != list(range(1, len(numeros) + 1)):
        raise ErreurImport("Les étapes doivent être numérotées de 1 à N, sans trou.")

    for numero in numeros:
        questions = par_etape[numero]
        if len(questions) > 4:
            raise ErreurImport(
                f"L'étape {numero} contient {len(questions)} questions (maximum 4)."
            )
        durees = {question.duree_s for question in questions}
        if len(durees) > 1:
            raise ErreurImport(
                f"L'étape {numero} a des durées différentes ; une étape a "
                "une seule durée."
            )
        for position, question in enumerate(questions, start=1):
            question.ordre = position
            question.couleur_slot = position

    return titre.strip(), normalisees


def valider_donnees(donnees) -> tuple[str, list[_QuestionNormalisee]]:
    """Valide un objet JSON et retourne le titre et les questions normalisées."""
    return _normaliser(donnees)


def importer_quiz(donnees, proprietaire) -> Quiz:
    """Valide puis crée le QCM en une transaction (tout ou rien)."""
    titre, questions = _normaliser(donnees)
    with transaction.atomic():
        quiz = Quiz.objects.create(titre=titre, proprietaire=proprietaire)
        etapes: dict[int, Step] = {}
        for question_normalisee in questions:
            etape = etapes.get(question_normalisee.etape)
            if etape is None:
                etape = Step.objects.create(
                    quiz=quiz,
                    numero=question_normalisee.etape,
                    duree_s=question_normalisee.duree_s,
                )
                etapes[question_normalisee.etape] = etape
            question = Question(
                quiz=quiz,
                step=etape,
                uid=question_normalisee.uid,
                enonce=question_normalisee.enonce,
                type=question_normalisee.type,
                afficher_indice_multiple=question_normalisee.afficher_indice_multiple,
                ordre=question_normalisee.ordre,
                couleur_slot=question_normalisee.couleur_slot,
            )
            try:
                question.full_clean()
            except ValidationError as exc:
                raise ErreurImport(
                    f"Question {question_normalisee.uid} invalide : {exc.messages}"
                ) from exc
            question.save()
            Choice.objects.bulk_create(
                [
                    Choice(
                        question=question,
                        lettre=choix["lettre"],
                        texte=choix["texte"],
                        est_correct=choix["correct"],
                        position=position,
                    )
                    for position, choix in enumerate(question_normalisee.choix)
                ]
            )
        return quiz


def charger_fichier(chemin: Path):
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

"""Exports CSV des résultats d'une séance.

Les fichiers sont encodés en UTF-8 avec BOM (``utf-8-sig``) et utilisent la
virgule comme séparateur, afin de s'ouvrir correctement dans Excel. Les notes
restent calculées à la volée par :func:`qcm.resultats.calculer_resultats` :
rien n'est stocké.
"""

import csv
import io

from qcm.resultats import calculer_resultats

BOM_UTF8 = "\ufeff"

ENTETE_NOTES = ("Nom", "Prénom", "Identifiant", "Note /20")
ENTETE_DETAIL = (
    "Nom",
    "Prénom",
    "Identifiant",
    "Question",
    "Réponse donnée",
    "Bonne réponse",
    "Points obtenus",
)


def _identifiant(participant) -> str:
    """Identifiant INSA s'il existe, sinon l'identifiant de connexion."""
    student = participant.student
    if student is None:
        return ""
    return student.identifiant_insa or student.code_etudiant


def _nom_complet(participant) -> tuple[str, str]:
    student = participant.student
    if student is None:
        return "", ""
    return student.nom, student.prenom


def _enonce_court(question, limite: int = 80) -> str:
    texte = " ".join(question.enonce.split())
    if len(texte) > limite:
        return f"{texte[:limite].rstrip()}…"
    return texte


def exporter_notes_csv(session, resultats: dict | None = None) -> str:
    """Export 1 : une ligne par élève, note /20 et lettre(s) par question.

    Les colonnes de questions reprennent l'``uid`` de chaque question dans
    l'ordre du QCM. Une case vide signifie que l'élève n'a pas répondu.
    """
    donnees = resultats if resultats is not None else calculer_resultats(session)
    questions = [stat["question"] for stat in donnees["stats_questions"]]

    tampon = io.StringIO()
    redacteur = csv.writer(tampon, delimiter=",")
    redacteur.writerow(
        [*ENTETE_NOTES, *[question.uid for question in questions]]
    )
    for ligne in donnees["lignes_participants"]:
        participant = ligne["participant"]
        nom, prenom = _nom_complet(participant)
        redacteur.writerow(
            [
                nom,
                prenom,
                _identifiant(participant),
                f"{ligne['note_20']:.2f}",
                *[
                    "".join(detail["lettres"])
                    for detail in ligne["notes"]
                ],
            ]
        )
    return BOM_UTF8 + tampon.getvalue()


def exporter_detail_csv(session, resultats: dict | None = None) -> str:
    """Export 2 : une ligne par élève et par question, avec les points."""
    donnees = resultats if resultats is not None else calculer_resultats(session)

    tampon = io.StringIO()
    redacteur = csv.writer(tampon, delimiter=",")
    redacteur.writerow(list(ENTETE_DETAIL))
    for ligne in donnees["lignes_participants"]:
        participant = ligne["participant"]
        nom, prenom = _nom_complet(participant)
        identifiant = _identifiant(participant)
        for detail in ligne["notes"]:
            question = detail["question"]
            redacteur.writerow(
                [
                    nom,
                    prenom,
                    identifiant,
                    f"{question.uid} — {_enonce_court(question)}",
                    "".join(detail["lettres"]),
                    "".join(detail["bonnes_lettres"]),
                    f"{detail['note']:.2f}",
                ]
            )
    return BOM_UTF8 + tampon.getvalue()

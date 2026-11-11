"""Import CSV des réponses papier d'une séance.

Format attendu : ``identifiant, uid_question, lettre_choisie``. L'identifiant
peut être le ``code_etudiant`` ou l'``identifiant_insa`` d'un élève. Une
question à choix multiple accepte plusieurs lettres dans la troisième colonne
(``AC``, ``A C`` ou ``A,C`` avec des guillemets CSV).

L'import est transactionnel : toutes les lignes sont validées avant la moindre
écriture. La règle « l'application prime » est appliquée : une ligne dont la
réponse existe déjà avec ``source='app'`` est ignorée, jamais modifiée. Une
réponse papier existante est mise à jour.
"""

import csv
import io
import re
import uuid
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from qcm import services
from qcm.models import Answer, Participant, Question, Student

ENTETE = ("identifiant", "uid_question", "lettre_choisie")


class ErreurImportPapier(ValueError):
    """Erreur de fichier ou de contenu, avec des messages lisibles."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        super().__init__(" ".join(self.messages))


@dataclass
class LigneReponsePapier:
    identifiant: str
    uid_question: str
    lettres: list[str]
    numero: int


def _decouper_lettres(valeur: str) -> list[str]:
    """Découpe ``A``, ``AC``, ``A C`` ou ``A,C`` en lettres uniques."""
    lettres = []
    for morceau in re.split(r"[\s,;]+", valeur.strip().upper()):
        for lettre in morceau:
            if lettre not in lettres:
                lettres.append(lettre)
    return lettres


def analyser_reponses(contenu: str) -> list[LigneReponsePapier]:
    """Lit le CSV et valide sa structure, sans toucher à la base."""
    lecteur = csv.reader(io.StringIO(contenu.lstrip("\ufeff")))
    try:
        entete = next(lecteur)
    except StopIteration:
        raise ErreurImportPapier("Le fichier CSV est vide.") from None

    entetes = [cellule.strip().lower() for cellule in entete]
    if len(entetes) != len(ENTETE) or set(entetes) != set(ENTETE):
        raise ErreurImportPapier(
            "En-tête CSV attendu : identifiant,uid_question,lettre_choisie."
        )
    index = {nom: entetes.index(nom) for nom in ENTETE}

    lignes = []
    vus: set[tuple[str, str]] = set()
    for numero, ligne in enumerate(lecteur, start=2):
        if not any(cellule.strip() for cellule in ligne):
            continue
        if len(ligne) != len(ENTETE):
            raise ErreurImportPapier(
                f"Ligne {numero} : {len(ligne)} colonne(s) au lieu de "
                f"{len(ENTETE)}."
            )
        identifiant = ligne[index["identifiant"]].strip()
        uid_question = ligne[index["uid_question"]].strip()
        brut = ligne[index["lettre_choisie"]].strip()
        if not identifiant:
            raise ErreurImportPapier(f"Ligne {numero} : identifiant vide.")
        if not uid_question:
            raise ErreurImportPapier(f"Ligne {numero} : uid_question vide.")
        lettres = _decouper_lettres(brut)
        if not lettres:
            raise ErreurImportPapier(
                f"Ligne {numero} : lettre_choisie vide."
            )
        cle = (identifiant.casefold(), uid_question)
        if cle in vus:
            raise ErreurImportPapier(
                f"Ligne {numero} : réponse en double pour "
                f"{identifiant} / {uid_question}."
            )
        vus.add(cle)
        lignes.append(
            LigneReponsePapier(
                identifiant=identifiant,
                uid_question=uid_question,
                lettres=lettres,
                numero=numero,
            )
        )

    if not lignes:
        raise ErreurImportPapier("Le fichier ne contient aucune réponse.")
    return lignes


def trouver_etudiant(identifiant: str) -> Student | None:
    """Cherche par code de connexion, puis par identifiant INSA."""
    return (
        Student.objects.filter(code_etudiant__iexact=identifiant).first()
        or Student.objects.filter(identifiant_insa__iexact=identifiant).first()
    )


def _valider_lignes(lignes, session) -> dict:
    """Résout élèves et questions, et valide les lettres avant écriture."""
    questions = services.questions_du_quiz(session.quiz)
    par_uid: dict[str, list[Question]] = {}
    for question in questions:
        par_uid.setdefault(question.uid, []).append(question)

    etudiants: dict[str, Student] = {}
    erreurs = []
    for ligne in lignes:
        prefixe = f"Ligne {ligne.numero}"
        cle_etudiant = ligne.identifiant.casefold()
        if cle_etudiant not in etudiants:
            etudiant = trouver_etudiant(ligne.identifiant)
            if etudiant is None:
                erreurs.append(
                    f"{prefixe} : aucun élève avec l'identifiant "
                    f"« {ligne.identifiant} »."
                )
                continue
            etudiants[cle_etudiant] = etudiant

        candidates = par_uid.get(ligne.uid_question, [])
        if not candidates:
            erreurs.append(
                f"{prefixe} : la question « {ligne.uid_question} » n'est pas "
                "dans le QCM de cette séance."
            )
            continue
        if len(candidates) > 1:
            erreurs.append(
                f"{prefixe} : l'uid « {ligne.uid_question} » est ambigu "
                "(plusieurs questions sélectionnées)."
            )
            continue
        question = candidates[0]
        lettres_disponibles = {
            choice.lettre for choice in question.choices.all()
        }
        if not set(ligne.lettres).issubset(lettres_disponibles):
            erreurs.append(
                f"{prefixe} : lettre(s) inconnue(s) pour la question "
                f"« {ligne.uid_question} »."
            )
            continue
        if (
            question.type == Question.TYPE_UNIQUE
            and len(ligne.lettres) > 1
        ):
            erreurs.append(
                f"{prefixe} : la question « {ligne.uid_question} » n'admet "
                "qu'une seule lettre."
            )

    if erreurs:
        raise ErreurImportPapier(erreurs)
    return etudiants


def importer_reponses(lignes, session) -> dict:
    """Écrit les réponses papier ; l'application prime sur le papier."""
    etudiants = _valider_lignes(lignes, session)
    questions = {
        question.uid: question
        for question in services.questions_du_quiz(session.quiz)
    }

    compteurs = {
        "creees": 0,
        "mises_a_jour": 0,
        "ignorees_app": 0,
        "participants_crees": 0,
    }
    try:
        with transaction.atomic():
            for ligne in lignes:
                etudiant = etudiants[ligne.identifiant.casefold()]
                participant = Participant.objects.filter(
                    session=session, student=etudiant
                ).first()
                if participant is None:
                    participant = Participant.objects.create(
                        session=session,
                        student=etudiant,
                        couleur_assignee=services.prochaine_couleur(session),
                    )
                    compteurs["participants_crees"] += 1

                question = questions[ligne.uid_question]
                existante = Answer.objects.filter(
                    participant=participant, question=question
                ).first()
                if existante is not None:
                    if existante.source == Answer.SOURCE_APP:
                        compteurs["ignorees_app"] += 1
                        continue
                    existante.choix_selectionnes = ligne.lettres
                    existante.save(update_fields=["choix_selectionnes"])
                    compteurs["mises_a_jour"] += 1
                    continue

                Answer.objects.create(
                    session=session,
                    participant=participant,
                    question=question,
                    choix_selectionnes=ligne.lettres,
                    source=Answer.SOURCE_PAPIER,
                    id_client=uuid.uuid4(),
                )
                compteurs["creees"] += 1
    except IntegrityError as exc:
        raise ErreurImportPapier(
            "Import annulé : une réponse existe déjà pour un élève et une "
            "question du fichier."
        ) from exc
    return compteurs

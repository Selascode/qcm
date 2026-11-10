"""Import de listes d'élèves (CSV ou JSON) et génération des identifiants.

La V2 n'utilise plus de PIN : chaque élève reçoit un identifiant lisible et
unique (``PRENOM-NOMnn``, ex. ``MARIE-DUP32``), suffisant pour rejoindre une
séance. L'identifiant est visible sur l'écran de pré-séance.
"""

import csv
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from qcm.models import Groupe, Student

LONGUEUR_MAX_NOM = 100


class ErreurImportParticipants(ValueError):
    """Erreur de fichier ou de contenu, avec une liste de messages lisibles."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        super().__init__(" ".join(self.messages))


@dataclass
class LigneEleve:
    nom: str
    prenom: str
    numero: int


def _charger_csv(chemin: Path) -> list[LigneEleve]:
    try:
        with open(chemin, newline="", encoding="utf-8-sig") as fichier:
            lecteur = csv.reader(fichier)
            try:
                entete = next(lecteur)
            except StopIteration:
                raise ErreurImportParticipants("Le fichier CSV est vide.") from None
            entetes = [cellule.strip().lower() for cellule in entete]
            if "nom" not in entetes or "prenom" not in entetes:
                raise ErreurImportParticipants(
                    "En-tête CSV manquant : les colonnes « nom » et « prenom » "
                    "sont obligatoires."
                )
            index_nom = entetes.index("nom")
            index_prenom = entetes.index("prenom")
            lignes = []
            for numero, ligne in enumerate(lecteur, start=2):
                if not any(cellule.strip() for cellule in ligne):
                    continue
                if len(ligne) != len(entete):
                    raise ErreurImportParticipants(
                        f"Ligne {numero} : {len(ligne)} colonne(s) au lieu de "
                        f"{len(entete)}."
                    )
                lignes.append(
                    LigneEleve(
                        nom=ligne[index_nom].strip(),
                        prenom=ligne[index_prenom].strip(),
                        numero=numero,
                    )
                )
            return lignes
    except FileNotFoundError as exc:
        raise ErreurImportParticipants(
            f"Fichier introuvable : {chemin}"
        ) from exc
    except OSError as exc:
        raise ErreurImportParticipants(
            f"Impossible de lire {chemin} : {exc}"
        ) from exc


def _charger_json(chemin: Path) -> list[LigneEleve]:
    try:
        with open(chemin, encoding="utf-8") as fichier:
            donnees = json.load(fichier)
    except FileNotFoundError as exc:
        raise ErreurImportParticipants(
            f"Fichier introuvable : {chemin}"
        ) from exc
    except OSError as exc:
        raise ErreurImportParticipants(
            f"Impossible de lire {chemin} : {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ErreurImportParticipants(
            f"JSON invalide ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}"
        ) from exc

    if not isinstance(donnees, list):
        raise ErreurImportParticipants(
            "Le fichier JSON doit contenir une liste d'objets {nom, prenom}."
        )

    lignes = []
    for numero, element in enumerate(donnees, start=1):
        if not isinstance(element, dict):
            raise ErreurImportParticipants(
                f"Élément {numero} : doit être un objet {{nom, prenom}}."
            )
        nom = element.get("nom")
        prenom = element.get("prenom")
        lignes.append(
            LigneEleve(
                nom=nom.strip() if isinstance(nom, str) else "",
                prenom=prenom.strip() if isinstance(prenom, str) else "",
                numero=numero,
            )
        )
    return lignes


def charger_fichier(chemin: Path) -> list[LigneEleve]:
    """Lit un CSV (``nom``, ``prenom``) ou un JSON (liste d'objets)."""
    suffixe = Path(chemin).suffix.lower()
    if suffixe == ".csv":
        return _charger_csv(Path(chemin))
    if suffixe == ".json":
        return _charger_json(Path(chemin))
    raise ErreurImportParticipants(
        f"Extension non reconnue pour {chemin} : utilisez un fichier .csv ou .json."
    )


def valider_lignes(lignes: list[LigneEleve], groupe: Groupe) -> None:
    """Valide toutes les lignes avant d'écrire quoi que ce soit."""
    if not lignes:
        raise ErreurImportParticipants("Le fichier ne contient aucun élève.")

    erreurs = []
    vus: dict[tuple[str, str], int] = {}
    for ligne in lignes:
        prefixe = f"Ligne {ligne.numero}"
        if not ligne.nom:
            erreurs.append(f"{prefixe} : le nom est vide.")
        elif len(ligne.nom) > LONGUEUR_MAX_NOM:
            erreurs.append(
                f"{prefixe} : le nom dépasse {LONGUEUR_MAX_NOM} caractères."
            )
        if not ligne.prenom:
            erreurs.append(f"{prefixe} : le prénom est vide.")
        elif len(ligne.prenom) > LONGUEUR_MAX_NOM:
            erreurs.append(
                f"{prefixe} : le prénom dépasse {LONGUEUR_MAX_NOM} caractères."
            )
        if not ligne.nom or not ligne.prenom:
            continue
        cle = (ligne.nom.casefold(), ligne.prenom.casefold())
        if cle in vus:
            erreurs.append(
                f"{prefixe} : doublon avec la ligne {vus[cle]} "
                f"({ligne.prenom} {ligne.nom})."
            )
        else:
            vus[cle] = ligne.numero

    existants = {
        (student.nom.casefold(), student.prenom.casefold())
        for student in Student.objects.filter(groupe=groupe).only("nom", "prenom")
    }
    for ligne in lignes:
        if not ligne.nom or not ligne.prenom:
            continue
        cle = (ligne.nom.casefold(), ligne.prenom.casefold())
        if cle in existants:
            erreurs.append(
                f"Ligne {ligne.numero} : {ligne.prenom} {ligne.nom} est déjà "
                f"présent dans le groupe « {groupe.nom} »."
            )

    if erreurs:
        raise ErreurImportParticipants(erreurs)


def _normaliser_texte(texte: str) -> str:
    normalise = (
        unicodedata.normalize("NFKD", texte)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return "".join(
        caractere for caractere in normalise if caractere.isalnum()
    ).upper()


def generer_code_etudiant(nom: str, prenom: str) -> str:
    """Identifiant lisible ``PRENOM-NOMnn`` (ex. ``MARIE-DUP32``), unique."""
    prenom_normalise = _normaliser_texte(prenom)[:20] or "ELEVE"
    nom_normalise = _normaliser_texte(nom)[:3] or "XXX"
    base = f"{prenom_normalise}-{nom_normalise}"
    for numero in range(100):
        code = f"{base}{numero:02d}"
        if not Student.objects.filter(code_etudiant=code).exists():
            return code
    raise ErreurImportParticipants(
        "Impossible de générer un identifiant unique pour "
        f"{prenom} {nom} : trop d'homonymes."
    )


def importer_participants(
    lignes: list[LigneEleve],
    groupe: Groupe,
) -> list[dict]:
    """Crée les élèves en une transaction et retourne leurs identifiants.

    Chaque entrée contient ``nom``, ``prenom`` et ``code_etudiant``. En cas
    d'erreur, aucune ligne n'est créée.
    """
    valider_lignes(lignes, groupe)
    resultats = []
    with transaction.atomic():
        for ligne in lignes:
            code = generer_code_etudiant(ligne.nom, ligne.prenom)
            Student.objects.create(
                nom=ligne.nom,
                prenom=ligne.prenom,
                code_etudiant=code,
                groupe=groupe,
            )
            resultats.append(
                {
                    "nom": ligne.nom,
                    "prenom": ligne.prenom,
                    "code_etudiant": code,
                }
            )
    return resultats

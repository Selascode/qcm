"""Commande ``import_participants`` : CSV/JSON vers élèves identifiés (V2)."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from qcm.import_participants import (
    ErreurImportParticipants,
    charger_fichier,
    ecrire_credentials,
    importer_participants,
)
from qcm.models import Groupe


class Command(BaseCommand):
    help = (
        "Importe des élèves (CSV nom,prenom ou JSON) dans un groupe, génère "
        "leur identifiant et leur PIN, et écrit un fichier d'identifiants."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "fichier",
            type=Path,
            help="Fichier .csv (en-tête nom,prenom) ou .json (liste d'objets).",
        )
        parser.add_argument(
            "--groupe",
            required=True,
            help="Nom du groupe existant dans lequel importer les élèves.",
        )
        parser.add_argument(
            "--identifiants",
            type=Path,
            default=None,
            help=(
                "Fichier JSON d'identifiants en clair à produire "
                "(défaut : identifiants_<groupe>.json). À supprimer après "
                "impression."
            ),
        )

    def handle(self, *args, **options) -> None:
        groupe = Groupe.objects.filter(nom=options["groupe"]).first()
        if groupe is None:
            raise CommandError(f"Groupe inconnu : {options['groupe']}")

        try:
            lignes = charger_fichier(options["fichier"])
            eleves = importer_participants(lignes, groupe)
        except ErreurImportParticipants as exc:
            for message in exc.messages:
                self.stderr.write(self.style.ERROR(message))
            raise CommandError("Import annulé, aucune ligne créée.") from exc

        chemin = options["identifiants"] or Path(
            f"identifiants_{slugify(groupe.nom)}.json"
        )
        ecrire_credentials(chemin, groupe, eleves)

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(eleves)} élève(s) importé(s) dans le groupe "
                f"« {groupe.nom} »."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"Identifiants et PIN en clair écrits dans {chemin} : "
                "distribuez la liste, puis supprimez ce fichier."
            )
        )

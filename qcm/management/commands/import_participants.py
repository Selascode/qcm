"""Commande ``import_participants`` : CSV/JSON vers élèves identifiés (V2)."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from qcm.import_participants import (
    ErreurImportParticipants,
    charger_fichier,
    importer_participants,
)
from qcm.models import Groupe


class Command(BaseCommand):
    help = (
        "Importe des élèves (CSV nom,prenom ou JSON) dans un groupe et génère "
        "leurs identifiants lisibles (sans PIN)."
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

    def handle(self, *args, **options) -> None:
        nom_groupe = str(options["groupe"]).strip()
        groupe = Groupe.objects.filter(nom__iexact=nom_groupe).first()
        if groupe is None:
            raise CommandError(f"Groupe inconnu : {options['groupe']}")

        try:
            lignes = charger_fichier(options["fichier"])
            eleves = importer_participants(lignes, groupe)
        except ErreurImportParticipants as exc:
            for message in exc.messages:
                self.stderr.write(self.style.ERROR(message))
            raise CommandError("Import annulé, aucune ligne créée.") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(eleves)} élève(s) importé(s) dans le groupe "
                f"« {groupe.nom} »."
            )
        )
        for eleve in eleves:
            self.stdout.write(
                f"  {eleve['prenom']} {eleve['nom']} : {eleve['code_etudiant']}"
            )

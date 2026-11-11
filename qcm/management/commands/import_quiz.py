"""Commande d'import d'un QCM historique (JSON) dans la banque de questions."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from qcm.import_questions import ErreurImport, charger_fichier_json, importer_quiz


class Command(BaseCommand):
    help = (
        "Importe un QCM depuis un fichier JSON : crée un ensemble de questions "
        "et un QCM qui les sélectionne, pour un professeur."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("fichier", type=Path, help="Chemin du fichier JSON.")
        parser.add_argument(
            "--proprietaire",
            required=True,
            help="Nom d'utilisateur du professeur propriétaire du QCM.",
        )

    def handle(self, *args, **options) -> None:
        utilisateur = get_user_model()
        try:
            proprietaire = utilisateur.objects.get(username=options["proprietaire"])
        except utilisateur.DoesNotExist as exc:
            raise CommandError(
                f"Utilisateur inconnu : {options['proprietaire']}"
            ) from exc

        try:
            donnees = charger_fichier_json(options["fichier"])
            quiz = importer_quiz(donnees, proprietaire)
        except ErreurImport as exc:
            for message in exc.messages:
                self.stderr.write(self.style.ERROR(message))
            raise CommandError("Import annulé.") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"QCM importé : {quiz.titre} (id={quiz.pk}, "
                f"{quiz.questions.count()} questions, ensemble "
                f"« {quiz.quiz_questions.first().question.set.nom} »)"
            )
        )

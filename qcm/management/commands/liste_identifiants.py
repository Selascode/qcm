"""Commande ``liste_identifiants`` : feuille imprimable nom, prénom, id, PIN."""

from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.html import escape
from django.utils.text import slugify

from qcm.import_participants import (
    ErreurImportParticipants,
    ecrire_credentials,
    generer_pin,
    lire_credentials,
)
from qcm.models import Groupe


class Command(BaseCommand):
    help = (
        "Produit une feuille HTML imprimable (nom, prénom, identifiant, PIN) "
        "pour un groupe. Les PIN ne sont stockés qu'en hash : la commande "
        "relit le fichier d'identifiants créé à l'import."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("groupe", help="Nom du groupe.")
        parser.add_argument(
            "--identifiants",
            type=Path,
            default=None,
            help="Fichier JSON d'identifiants (défaut : identifiants_<groupe>.json).",
        )
        parser.add_argument(
            "--sortie",
            type=Path,
            default=None,
            help="Fichier HTML à produire (défaut : identifiants_<groupe>.html).",
        )
        parser.add_argument(
            "--regenerer",
            action="store_true",
            help=(
                "Régénère tous les PIN du groupe et réécrit le fichier "
                "d'identifiants. À n'utiliser que si la liste est perdue : les "
                "anciens PIN sont invalidés."
            ),
        )

    def handle(self, *args, **options) -> None:
        groupe = Groupe.objects.filter(nom=options["groupe"]).first()
        if groupe is None:
            raise CommandError(f"Groupe inconnu : {options['groupe']}")

        chemin = options["identifiants"] or Path(
            f"identifiants_{slugify(groupe.nom)}.json"
        )

        if options["regenerer"]:
            eleves = self._regenerer(groupe)
            ecrire_credentials(chemin, groupe, eleves)
            self.stdout.write(
                self.style.WARNING(
                    "PIN régénérés : les anciennes feuilles ne sont plus valides."
                )
            )
        else:
            try:
                donnees = lire_credentials(chemin)
            except ErreurImportParticipants as exc:
                raise CommandError(" ".join(exc.messages)) from exc
            if donnees.get("groupe") != groupe.nom:
                raise CommandError(
                    f"Le fichier d'identifiants concerne « "
                    f"{donnees.get('groupe')} », pas « {groupe.nom} »."
                )
            eleves = donnees["eleves"]

        sortie = options["sortie"] or Path(
            f"identifiants_{slugify(groupe.nom)}.html"
        )
        sortie = Path(sortie)
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(self._html(groupe, eleves), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Feuille imprimable écrite dans {sortie} "
                f"({len(eleves)} élève(s))."
            )
        )

    def _regenerer(self, groupe: Groupe) -> list[dict]:
        eleves = []
        with transaction.atomic():
            for student in groupe.etudiants.order_by("nom", "prenom"):
                pin = generer_pin()
                student.pin_hash = make_password(pin)
                student.save(update_fields=["pin_hash"])
                eleves.append(
                    {
                        "nom": student.nom,
                        "prenom": student.prenom,
                        "code_etudiant": student.code_etudiant,
                        "pin": pin,
                    }
                )
        return eleves

    def _html(self, groupe: Groupe, eleves: list[dict]) -> str:
        lignes = "\n".join(
            "<tr>"
            f"<td>{escape(e['nom'])}</td>"
            f"<td>{escape(e['prenom'])}</td>"
            f"<td class=\"identifiant\">{escape(e['code_etudiant'])}</td>"
            f"<td class=\"pin\">{escape(e['pin'])}</td>"
            "</tr>"
            for e in eleves
        )
        return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Identifiants — {escape(groupe.nom)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1b1b1b; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
  p.avertissement {{ color: #8a4b00; font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1.5rem; }}
  th, td {{ border: 1px solid #b9b3a7; padding: 0.5rem 0.7rem; text-align: left; }}
  th {{ background: #eee9df; }}
  td.pin, td.identifiant {{ font-family: ui-monospace, monospace; font-size: 1.05rem; }}
  @media print {{
    body {{ margin: 0.5cm; }}
    p.avertissement {{ display: none; }}
    tr {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<h1>Identifiants — {escape(groupe.nom)}</h1>
<p>À remettre individuellement. Ne pas afficher au tableau.</p>
<p class="avertissement">
  Document confidentiel : supprimez-le après impression. Un appareil actif par
  élève ; une nouvelle connexion remplace l'ancienne.
</p>
<table>
<thead><tr><th>Nom</th><th>Prénom</th><th>Identifiant</th><th>PIN</th></tr></thead>
<tbody>
{lignes}
</tbody>
</table>
</body>
</html>
"""

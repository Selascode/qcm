"""Import des participants (CLI) et génération des identifiants sans PIN."""

import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from qcm import import_participants as module
from qcm.models import Student

pytestmark = pytest.mark.django_db

CSV_EXEMPLE = "nom,prenom\nDupont,Marie\nMartin,Paul\n"


def _ecrire(chemin, contenu: str):
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def _importer(chemin, groupe):
    sortie = io.StringIO()
    call_command(
        "import_participants",
        str(chemin),
        groupe=groupe.nom,
        stdout=sortie,
    )
    return sortie.getvalue()


def test_import_csv_genere_identifiants_lisibles_sans_pin(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)

    sortie = _importer(chemin, groupe)

    assert "2 élève(s)" in sortie
    students = list(Student.objects.order_by("nom"))
    assert [student.code_etudiant for student in students] == [
        "MARIE-DUP00",
        "PAUL-MAR00",
    ]
    assert not hasattr(students[0], "pin_hash")
    assert "MARIE-DUP00" in sortie


def test_import_json_codes(tmp_path, groupe):
    chemin = _ecrire(
        tmp_path / "eleves.json",
        json.dumps(
            [
                {"nom": "Durand", "prenom": "Alice"},
                {"nom": "Petit", "prenom": "Benoit"},
            ]
        ),
    )

    _importer(chemin, groupe)

    codes = sorted(Student.objects.values_list("code_etudiant", flat=True))
    assert codes == ["ALICE-DUR00", "BENOIT-PET00"]


def test_import_groupe_nom_insensible_a_la_casse(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)
    sortie = io.StringIO()

    call_command(
        "import_participants",
        str(chemin),
        groupe="isia4",
        stdout=sortie,
    )

    assert Student.objects.filter(groupe=groupe).count() == 2


def test_import_csv_en_tete_manquant(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", "prenom\nMarie\n")

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 0


def test_import_csv_doublon_dans_le_fichier(tmp_path, groupe):
    chemin = _ecrire(
        tmp_path / "eleves.csv",
        "nom,prenom\nDupont,Marie\nDupont,Marie\n",
    )

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 0


def test_import_csv_fichier_vide(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", "nom,prenom\n")

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 0


def test_import_groupe_inconnu(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)

    with pytest.raises(CommandError):
        call_command(
            "import_participants",
            str(chemin),
            groupe="INCONNU",
            stdout=io.StringIO(),
        )

    assert Student.objects.count() == 0


def test_import_extension_non_reconnue(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.txt", CSV_EXEMPLE)

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 0


def test_import_eleve_deja_present_refuse(tmp_path, groupe):
    from qcm.tests.helpers import creer_eleve

    creer_eleve(groupe, nom="Dupont", prenom="Marie")
    chemin = _ecrire(tmp_path / "eleves.csv", "nom,prenom\nDupont,Marie\n")

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 1


def test_import_transactionnel_echec_aucune_ligne(tmp_path, groupe, monkeypatch):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)
    compteur = {"n": 0}

    def generer_qui_echoue(nom, prenom):
        compteur["n"] += 1
        if compteur["n"] == 2:
            raise module.ErreurImportParticipants("échec simulé")
        return f"XX{compteur['n']:02d}"

    monkeypatch.setattr(module, "generer_code_etudiant", generer_qui_echoue)

    with pytest.raises(CommandError):
        _importer(chemin, groupe)

    assert Student.objects.count() == 0


def test_generer_code_etudiant_unique(groupe):
    Student.objects.create(
        nom="Dupont",
        prenom="Marie",
        code_etudiant=module.generer_code_etudiant("Dupont", "Marie"),
        groupe=groupe,
    )

    second = module.generer_code_etudiant("Dupont", "Marie")
    assert second == "MARIE-DUP01"

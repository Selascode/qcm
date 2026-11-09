"""Import des participants, génération des identifiants et liste imprimable."""

import io
import json

import pytest
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.core.management.base import CommandError

from qcm import import_participants as module
from qcm.models import Student

pytestmark = pytest.mark.django_db

CSV_EXEMPLE = "nom,prenom\nDupont,Marie\nMartin,Paul\n"


def _ecrire(chemin, contenu: str):
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def _importer(chemin, groupe, identifiants):
    sortie = io.StringIO()
    call_command(
        "import_participants",
        str(chemin),
        groupe=groupe.nom,
        identifiants=str(identifiants),
        stdout=sortie,
    )
    return sortie.getvalue()


def test_import_csv_genere_identifiant_et_pin(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)
    identifiants = tmp_path / "identifiants.json"

    sortie = _importer(chemin, groupe, identifiants)

    assert "2 élève(s)" in sortie
    assert Student.objects.filter(groupe=groupe).count() == 2
    donnees = json.loads(identifiants.read_text(encoding="utf-8"))
    assert donnees["groupe"] == groupe.nom
    assert len(donnees["eleves"]) == 2

    for eleve in donnees["eleves"]:
        student = Student.objects.get(code_etudiant=eleve["code_etudiant"])
        assert student.groupe == groupe
        assert student.pin_hash != eleve["pin"]
        assert check_password(eleve["pin"], student.pin_hash)
        assert len(eleve["pin"]) == 6
        assert eleve["pin"].isdigit()


def test_import_json(tmp_path, groupe):
    chemin = _ecrire(
        tmp_path / "eleves.json",
        json.dumps(
            [
                {"nom": "Durand", "prenom": "Alice"},
                {"nom": "Petit", "prenom": "Benoît"},
            ],
            ensure_ascii=False,
        ),
    )
    identifiants = tmp_path / "identifiants.json"

    _importer(chemin, groupe, identifiants)

    assert sorted(
        Student.objects.values_list("prenom", flat=True)
    ) == ["Alice", "Benoît"]


def test_import_csv_en_tete_manquant(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", "prenom\nMarie\n")

    with pytest.raises(CommandError):
        _importer(chemin, groupe, tmp_path / "identifiants.json")

    assert Student.objects.count() == 0


def test_import_csv_doublon_dans_le_fichier(tmp_path, groupe):
    chemin = _ecrire(
        tmp_path / "eleves.csv",
        "nom,prenom\nDupont,Marie\nDupont,Marie\n",
    )

    with pytest.raises(CommandError):
        _importer(chemin, groupe, tmp_path / "identifiants.json")

    assert Student.objects.count() == 0


def test_import_csv_fichier_vide(tmp_path, groupe):
    chemin = _ecrire(tmp_path / "eleves.csv", "nom,prenom\n")

    with pytest.raises(CommandError):
        _importer(chemin, groupe, tmp_path / "identifiants.json")

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
        _importer(chemin, groupe, tmp_path / "identifiants.json")

    assert Student.objects.count() == 0


def test_import_eleve_deja_present_refuse(tmp_path, groupe):
    from qcm.tests.helpers import creer_eleve

    creer_eleve(groupe, nom="Dupont", prenom="Marie")
    chemin = _ecrire(
        tmp_path / "eleves.csv",
        "nom,prenom\nDupont,Marie\n",
    )

    with pytest.raises(CommandError):
        _importer(chemin, groupe, tmp_path / "identifiants.json")

    assert Student.objects.count() == 1


def test_import_transactionnel_echec_aucune_ligne(tmp_path, groupe, monkeypatch):
    chemin = _ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)
    compteur = {"n": 0}

    def generer_qui_echoue(nom, prenom):
        compteur["n"] += 1
        if compteur["n"] == 2:
            raise module.ErreurImportParticipants("échec simulé")
        return f"XX{compteur['n']:04d}"

    monkeypatch.setattr(module, "generer_code_etudiant", generer_qui_echoue)

    with pytest.raises(CommandError):
        _importer(chemin, groupe, tmp_path / "identifiants.json")

    assert Student.objects.count() == 0


def test_liste_identifiants_produit_le_html(tmp_path, groupe):
    import_command = "import_participants"
    identifiants = tmp_path / "identifiants.json"
    call_command(
        import_command,
        str(_ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)),
        groupe=groupe.nom,
        identifiants=str(identifiants),
        stdout=io.StringIO(),
    )
    feuille = tmp_path / "identifiants.html"

    call_command(
        "liste_identifiants",
        groupe.nom,
        identifiants=str(identifiants),
        sortie=str(feuille),
        stdout=io.StringIO(),
    )

    contenu = feuille.read_text(encoding="utf-8")
    assert "Dupont" in contenu
    assert "Marie" in contenu
    assert "Identifiant" in contenu
    assert "PIN" in contenu
    assert "pin_hash" not in contenu
    donnees = json.loads(identifiants.read_text(encoding="utf-8"))
    for eleve in donnees["eleves"]:
        assert eleve["code_etudiant"] in contenu
        assert eleve["pin"] in contenu


def test_liste_identifiants_sans_fichier_echoue(tmp_path, groupe):
    with pytest.raises(CommandError):
        call_command(
            "liste_identifiants",
            groupe.nom,
            identifiants=str(tmp_path / "absent.json"),
            sortie=str(tmp_path / "feuille.html"),
            stdout=io.StringIO(),
        )


def test_liste_identifiants_regenerer(tmp_path, groupe):
    identifiants = tmp_path / "identifiants.json"
    call_command(
        "import_participants",
        str(_ecrire(tmp_path / "eleves.csv", CSV_EXEMPLE)),
        groupe=groupe.nom,
        identifiants=str(identifiants),
        stdout=io.StringIO(),
    )
    anciens = {
        student.code_etudiant: student.pin_hash
        for student in Student.objects.all()
    }

    call_command(
        "liste_identifiants",
        groupe.nom,
        identifiants=str(identifiants),
        sortie=str(tmp_path / "feuille.html"),
        regenerer=True,
        stdout=io.StringIO(),
    )

    nouveaux = json.loads(identifiants.read_text(encoding="utf-8"))
    assert len(nouveaux["eleves"]) == 2
    for eleve in nouveaux["eleves"]:
        student = Student.objects.get(code_etudiant=eleve["code_etudiant"])
        assert student.pin_hash != anciens[eleve["code_etudiant"]]
        assert check_password(eleve["pin"], student.pin_hash)

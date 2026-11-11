"""Import web des élèves et export des identifiants (V2)."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from qcm.models import Student
from qcm.tests.helpers import creer_eleve

pytestmark = pytest.mark.django_db

CSV = b"nom,prenom\nDupont,Marie\nMartin,Paul\n"
JSON = b'[{"nom": "Durand", "prenom": "Alice"}]'


def _url(groupe):
    return reverse("qcm:importer_eleves", args=[groupe.pk])


def test_page_import_accessible_au_proprietaire(client, proprietaire, groupe):
    client.force_login(proprietaire)

    reponse = client.get(_url(groupe))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "Importer des élèves" in contenu
    assert reverse("qcm:exporter_identifiants", args=[groupe.pk, "csv"]) in contenu
    assert reverse("qcm:exporter_identifiants", args=[groupe.pk, "json"]) in contenu


def test_page_import_refusee_a_un_autre_professeur(
    client, autre_proprietaire, groupe
):
    client.force_login(autre_proprietaire)

    assert client.get(_url(groupe)).status_code == 404


def test_page_import_anonyme_redirige(client, groupe):
    assert client.get(_url(groupe)).status_code == 302


def test_import_web_csv(client, proprietaire, groupe):
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile("eleves.csv", CSV, content_type="text/csv")

    reponse = client.post(_url(groupe), {"fichier": fichier})

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "2 élève(s) importé(s)" in contenu
    assert Student.objects.filter(groupe=groupe).count() == 2
    assert "MARIE-DUP00" in contenu
    assert "PAUL-MAR00" in contenu


def test_import_web_json(client, proprietaire, groupe):
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile("eleves.json", JSON, content_type="application/json")

    reponse = client.post(_url(groupe), {"fichier": fichier})

    assert reponse.status_code == 200
    assert Student.objects.filter(groupe=groupe).count() == 1
    assert Student.objects.get().code_etudiant == "ALICE-DUR00"


def test_import_web_fichier_invalide(client, proprietaire, groupe):
    client.force_login(proprietaire)
    fichier = SimpleUploadedFile("eleves.csv", b"prenom\nMarie\n")

    reponse = client.post(_url(groupe), {"fichier": fichier})

    assert reponse.status_code == 200
    assert "En-tête CSV manquant" in reponse.content.decode()
    assert Student.objects.count() == 0


def test_export_csv(client, proprietaire, groupe):
    creer_eleve(groupe, nom="Dupont", prenom="Marie", code_etudiant="MARIE-DUP00")
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:exporter_identifiants", args=[groupe.pk, "csv"])
    )

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "nom,prenom,code_etudiant" in contenu
    assert "MARIE-DUP00" in contenu
    assert "pin" not in contenu.lower()


def test_export_json(client, proprietaire, groupe):
    creer_eleve(groupe, nom="Dupont", prenom="Marie", code_etudiant="MARIE-DUP00")
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:exporter_identifiants", args=[groupe.pk, "json"])
    )

    assert reponse.status_code == 200
    donnees = json.loads(reponse.content.decode())
    assert donnees == [
        {"nom": "Dupont", "prenom": "Marie", "code_etudiant": "MARIE-DUP00"}
    ]
    assert "pin" not in json.dumps(donnees).lower()


def test_export_refuse_a_un_autre_professeur(
    client, autre_proprietaire, groupe
):
    client.force_login(autre_proprietaire)

    reponse = client.get(
        reverse("qcm:exporter_identifiants", args=[groupe.pk, "csv"])
    )

    assert reponse.status_code == 404


def test_import_web_csv_avec_identifiant_insa(client, proprietaire, groupe):
    client.force_login(proprietaire)
    contenu = b"nom,prenom,identifiant_insa\nDupont,Marie,INS-42\n"
    fichier = SimpleUploadedFile("eleves.csv", contenu, content_type="text/csv")

    reponse = client.post(_url(groupe), {"fichier": fichier})

    assert reponse.status_code == 200
    assert "INS-42" in reponse.content.decode()
    assert Student.objects.get().identifiant_insa == "INS-42"

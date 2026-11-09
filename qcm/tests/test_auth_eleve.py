"""Authentification élève : identifiant + PIN, un seul appareil actif (V2)."""

import json

import pytest

from qcm.import_json import importer_quiz
from qcm.models import Participant, Session
from qcm.tests.helpers import (
    creer_eleve,
    creer_groupe,
    donnees_quiz,
    etat,
    rejoindre_eleve,
    repondre,
)

pytestmark = pytest.mark.django_db

CLES_INTERDITES = {"enonce", "texte", "est_correct", "pin", "pin_hash"}


def verifier_cles(valeur) -> None:
    if isinstance(valeur, dict):
        for cle, sous_valeur in valeur.items():
            assert cle not in CLES_INTERDITES, f"clé interdite : {cle}"
            verifier_cles(sous_valeur)
    elif isinstance(valeur, list):
        for sous_valeur in valeur:
            verifier_cles(sous_valeur)


@pytest.fixture
def session_groupe(proprietaire, groupe):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    return Session.objects.create(quiz=quiz, groupe=groupe)


def test_connexion_groupe_avec_pin(client, groupe, session_groupe):
    student = creer_eleve(groupe, code_etudiant="MD0001", pin="123456")

    reponse = rejoindre_eleve(client, session_groupe, "MD0001", "123456")

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["ok"] is True
    participant = Participant.objects.get(pk=donnees["participant_id"])
    assert participant.student == student
    assert participant.derniere_activite is not None


def test_identifiant_insensible_a_la_casse(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")

    assert rejoindre_eleve(client, session_groupe, "md0001", "123456").status_code == 200


def test_pin_faux_et_identifiant_inconnu_meme_reponse(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")

    pin_faux = rejoindre_eleve(client, session_groupe, "MD0001", "000000")
    inconnu = rejoindre_eleve(client, session_groupe, "ZZ9999", "123456")

    assert pin_faux.status_code == 401
    assert inconnu.status_code == 401
    assert pin_faux.json() == inconnu.json()
    assert pin_faux.json()["raison"] == "identifiants_invalides"


def test_identifiants_requis_pour_une_seance_de_groupe(client, session_groupe):
    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session_groupe.code_session}),
        content_type="application/json",
    )

    assert reponse.status_code == 401
    assert reponse.json()["raison"] == "identifiants_requis"


def test_eleve_d_un_autre_groupe_refuse(client, proprietaire, groupe, session_groupe):
    autre_groupe = creer_groupe(proprietaire, nom="Autre")
    creer_eleve(autre_groupe, code_etudiant="AA0001", pin="123456")

    reponse = rejoindre_eleve(client, session_groupe, "AA0001", "123456")

    assert reponse.status_code == 401
    assert reponse.json()["raison"] == "identifiants_invalides"


def test_un_seul_appareil_actif(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")

    premier = rejoindre_eleve(client, session_groupe, "MD0001", "123456")
    jeton_ancien = premier.json()["jeton"]
    second = rejoindre_eleve(client, session_groupe, "MD0001", "123456")
    jeton_nouveau = second.json()["jeton"]

    assert Participant.objects.count() == 1
    assert jeton_ancien != jeton_nouveau
    assert etat(client, jeton_ancien).status_code == 401
    assert etat(client, jeton_nouveau).status_code == 200


def test_ancien_appareil_ne_peut_plus_repondre(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")
    jeton_ancien = rejoindre_eleve(
        client, session_groupe, "MD0001", "123456"
    ).json()["jeton"]
    rejoindre_eleve(client, session_groupe, "MD0001", "123456")

    reponse = repondre(
        client,
        jeton_ancien,
        "E1Q1",
        ["A"],
    )

    assert reponse.status_code == 401


def test_seance_libre_reste_anonyme(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz)

    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session.code_session}),
        content_type="application/json",
    )

    assert reponse.status_code == 200
    participant = Participant.objects.get(pk=reponse.json()["participant_id"])
    assert participant.student is None


def test_join_groupe_ne_fuite_aucun_contenu(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")

    join = rejoindre_eleve(client, session_groupe, "MD0001", "123456")
    jeton = join.json()["jeton"]

    for reponse in (join, etat(client, jeton)):
        contenu = reponse.content.decode()
        verifier_cles(reponse.json())
        assert "123456" not in contenu
        assert "pin_hash" not in contenu


def test_page_rejoindre_groupe_affiche_identifiant_et_pin(
    client, groupe, session_groupe
):
    contenu = client.get(f"/rejoindre/{session_groupe.code_session}/").content.decode()

    assert 'id="code_etudiant"' in contenu
    assert 'id="pin"' in contenu


def test_page_rejoindre_demo_sans_pin(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz)

    contenu = client.get(f"/rejoindre/{session.code_session}/").content.decode()

    assert 'id="code_etudiant"' not in contenu
    assert 'id="pin"' not in contenu

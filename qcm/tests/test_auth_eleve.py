"""Authentification élève : identifiant seul, un appareil actif (V2)."""

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


def test_connexion_groupe_avec_identifiant(client, groupe, session_groupe):
    student = creer_eleve(groupe, code_etudiant="MD0001")

    reponse = rejoindre_eleve(client, session_groupe, "MD0001")

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["ok"] is True
    participant = Participant.objects.get(pk=donnees["participant_id"])
    assert participant.student == student
    assert participant.derniere_activite is not None


def test_identifiant_insensible_a_la_casse(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001")

    assert rejoindre_eleve(client, session_groupe, "md0001").status_code == 200


def test_identifiant_inconnu_refuse(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001")

    reponse = rejoindre_eleve(client, session_groupe, "ZZ9999")

    assert reponse.status_code == 404
    assert reponse.json()["raison"] == "identifiant_inconnu"


def test_identifiant_requis_pour_une_seance_de_groupe(client, session_groupe):
    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session_groupe.code_session}),
        content_type="application/json",
    )

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "identifiant_requis"


def test_eleve_d_un_autre_groupe_refuse(client, proprietaire, groupe, session_groupe):
    autre_groupe = creer_groupe(proprietaire, nom="Autre")
    creer_eleve(autre_groupe, code_etudiant="AA0001")

    reponse = rejoindre_eleve(client, session_groupe, "AA0001")

    assert reponse.status_code == 404
    assert reponse.json()["raison"] == "identifiant_inconnu"


def test_un_seul_appareil_actif(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001")

    premier = rejoindre_eleve(client, session_groupe, "MD0001")
    jeton_ancien = premier.json()["jeton"]
    second = rejoindre_eleve(client, session_groupe, "MD0001")
    jeton_nouveau = second.json()["jeton"]

    assert Participant.objects.count() == 1
    assert jeton_ancien != jeton_nouveau
    assert etat(client, jeton_ancien).status_code == 401
    assert etat(client, jeton_nouveau).status_code == 200


def test_ancien_appareil_ne_peut_plus_repondre(client, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001")
    jeton_ancien = rejoindre_eleve(client, session_groupe, "MD0001").json()["jeton"]
    rejoindre_eleve(client, session_groupe, "MD0001")

    reponse = repondre(client, jeton_ancien, "E1Q1", ["A"])

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
    creer_eleve(groupe, code_etudiant="MD0001")

    join = rejoindre_eleve(client, session_groupe, "MD0001")
    jeton = join.json()["jeton"]

    for reponse in (join, etat(client, jeton)):
        contenu = reponse.content.decode()
        verifier_cles(reponse.json())
        assert "pin_hash" not in contenu


def test_page_rejoindre_groupe_affiche_identifiant_sans_pin(
    client, groupe, session_groupe
):
    contenu = client.get(f"/rejoindre/{session_groupe.code_session}/").content.decode()

    assert 'id="code_etudiant"' in contenu
    assert 'id="pin"' not in contenu


def test_page_rejoindre_demo_sans_identifiant(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz)

    contenu = client.get(f"/rejoindre/{session.code_session}/").content.decode()

    assert 'id="code_etudiant"' not in contenu


def test_couleurs_round_robin_et_reconnexion(client, groupe, session_groupe):
    etudiants = [
        creer_eleve(
            groupe,
            nom=f"Nom{index}",
            prenom=f"Prenom{index}",
            code_etudiant=f"ELEVE{index}",
        )
        for index in range(1, 6)
    ]

    for etudiant in etudiants[:4]:
        assert (
            rejoindre_eleve(
                client, session_groupe, etudiant.code_etudiant
            ).status_code
            == 200
        )

    participants = list(
        Participant.objects.filter(session=session_groupe).order_by("id")
    )
    assert [participant.couleur_assignee for participant in participants] == [
        1,
        2,
        3,
        4,
    ]

    assert (
        rejoindre_eleve(
            client, session_groupe, etudiants[4].code_etudiant
        ).status_code
        == 200
    )
    cinquieme = Participant.objects.get(student=etudiants[4])
    assert cinquieme.couleur_assignee == 1

    premier = Participant.objects.get(student=etudiants[0])
    rejoindre_eleve(client, session_groupe, etudiants[0].code_etudiant)
    premier.refresh_from_db()
    assert premier.couleur_assignee == 1
    assert Participant.objects.filter(session=session_groupe).count() == 5


def test_couleurs_round_robin_en_seance_libre(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz)

    for _ in range(5):
        reponse = client.post(
            "/api/rejoindre/",
            data=json.dumps({"code": session.code_session}),
            content_type="application/json",
        )
        assert reponse.status_code == 200

    participants = list(
        Participant.objects.filter(session=session).order_by("id")
    )
    assert [participant.couleur_assignee for participant in participants] == [
        1,
        2,
        3,
        4,
        1,
    ]

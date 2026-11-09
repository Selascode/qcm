"""API élève : connexion, reconnexion et états de séance."""

import json

import pytest

from qcm.import_json import importer_quiz
from qcm.models import Participant
from qcm.services import mettre_en_pause, reprendre
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    rejoindre,
)

pytestmark = pytest.mark.django_db


def test_rejoindre_puis_reconnexion_avec_le_meme_jeton(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)

    premier = rejoindre(client, session)
    assert premier["couleur"]["hex"].startswith("#")
    assert premier["couleur"]["symbole"] in ("●", "▲", "■", "◆")

    seconde = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session.code_session, "jeton": premier["jeton"]}),
        content_type="application/json",
    )

    assert seconde.status_code == 200
    assert seconde.json()["participant_id"] == premier["participant_id"]
    assert Participant.objects.count() == 1


def test_rejoindre_avec_jeton_inconnu_cree_un_nouveau_participant(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)

    premier = rejoindre(client, session)
    seconde = client.post(
        "/api/rejoindre/",
        data=json.dumps(
            {
                "code": session.code_session,
                "jeton": "00000000-0000-4000-8000-000000000000",
            }
        ),
        content_type="application/json",
    )

    assert seconde.json()["participant_id"] != premier["participant_id"]
    assert Participant.objects.count() == 2


def test_rejoindre_code_inconnu(client):
    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": "ZZZZZZ"}),
        content_type="application/json",
    )

    assert reponse.status_code == 404
    assert reponse.json()["raison"] == "code_inconnu"


def test_rejoindre_json_invalide(client):
    reponse = client.post(
        "/api/rejoindre/",
        data="{",
        content_type="application/json",
    )

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "json_invalide"


def test_etat_sans_jeton_est_refuse(client):
    assert client.get("/api/etat/").status_code == 401
    assert (
        client.get("/api/etat/", headers={"X-Jeton": "pas-un-uuid"}).status_code == 401
    )


def test_etats_attente_en_cours_pause_fini(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1, duree_s=60), proprietaire)
    session = creer_session(quiz)
    participant = rejoindre(client, session)
    jeton = participant["jeton"]

    donnees = etat(client, jeton).json()
    assert donnees["statut"] == "attente"
    assert donnees["question_uid"] is None
    assert donnees["lettres"] == []

    session = demarrer(session)
    donnees = etat(client, jeton).json()
    assert donnees["statut"] == "en_cours"
    assert donnees["etape"] == 1
    assert donnees["nb_etapes"] == 1
    assert donnees["question_uid"] == "E1Q1"
    assert donnees["nb_choix"] == 3
    assert set(donnees["lettres"]) == {"A", "B", "C"}
    assert 0 <= donnees["temps_restant_s"] <= 60
    assert donnees["deja_repondu"] is False

    session = mettre_en_pause(session)
    donnees = etat(client, jeton).json()
    assert donnees["statut"] == "pause"
    assert donnees["temps_restant_s"] == session.reste_en_pause

    session = reprendre(session)
    assert etat(client, jeton).json()["statut"] == "en_cours"

    expirer_etape(session)
    donnees = etat(client, jeton).json()
    assert donnees["statut"] == "fini"
    assert donnees["question_uid"] is None


def test_deja_repondu_apres_une_reponse(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    demarrer(session)
    participant = rejoindre(client, session)
    question_uid = etat(client, participant["jeton"]).json()["question_uid"]

    client.post(
        "/api/repondre/",
        data=json.dumps(
            {
                "id_client": "11111111-1111-4111-8111-111111111111",
                "question_uid": question_uid,
                "choix": ["A"],
            }
        ),
        content_type="application/json",
        headers={"X-Jeton": participant["jeton"]},
    )

    donnees = etat(client, participant["jeton"]).json()
    assert donnees["deja_repondu"] is True
    assert donnees["question_uid"] == question_uid


def test_ordre_des_lettres_stable_entre_deux_appels(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    demarrer(session)
    participant = rejoindre(client, session)

    premier = etat(client, participant["jeton"]).json()["lettres"]
    second = etat(client, participant["jeton"]).json()["lettres"]

    assert premier == second
    assert sorted(premier) == ["A", "B", "C"]

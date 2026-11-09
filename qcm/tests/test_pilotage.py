"""Pilotage professeur : actions, authentification et CSRF."""

import json

import pytest
from django.test import Client

from qcm.import_json import importer_quiz
from qcm.models import Session
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    piloter,
)

pytestmark = pytest.mark.django_db


def preparer(proprietaire):
    quiz = importer_quiz(donnees_quiz(2, 1, duree_s=60), proprietaire)
    return creer_session(quiz)


def test_actions_de_pilotage(client, proprietaire):
    session = preparer(proprietaire)
    client.force_login(proprietaire)

    reponse = piloter(client, session, "demarrer")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "en_cours"
    session.refresh_from_db()
    assert session.statut == Session.STATUT_EN_COURS

    reponse = piloter(client, session, "pause")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "pause"

    reponse = piloter(client, session, "reprendre")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "en_cours"
    session.refresh_from_db()
    avant = session.ends_at

    reponse = piloter(client, session, "plus_temps", 60)
    assert reponse.status_code == 200
    session.refresh_from_db()
    assert (session.ends_at - avant).total_seconds() == 60

    reponse = piloter(client, session, "suivant")
    assert reponse.status_code == 200
    assert reponse.json()["etape"] == 2

    reponse = piloter(client, session, "precedent")
    assert reponse.status_code == 200
    assert reponse.json()["etape"] == 1


def test_action_refusee_dans_le_mauvais_etat(client, proprietaire):
    session = preparer(proprietaire)
    client.force_login(proprietaire)

    reponse = piloter(client, session, "pause")

    assert reponse.status_code == 409
    assert reponse.json()["ok"] is False
    assert "pas en cours" in reponse.json()["raison"]


def test_action_inconnue(client, proprietaire):
    session = preparer(proprietaire)
    client.force_login(proprietaire)

    reponse = piloter(client, session, "exploser")

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "action_inconnue"


def test_tableau_et_api_proteges(client, proprietaire, autre_proprietaire):
    session = preparer(proprietaire)
    url_tableau = f"/tableau/{session.code_session}/"
    url_etat = f"/api/etat_prof/?code={session.code_session}"

    anonyme = Client()
    assert anonyme.get(url_tableau).status_code == 302
    assert anonyme.get(url_etat).status_code == 302
    assert (
        anonyme.post(
            "/api/piloter/",
            data=json.dumps({"code": session.code_session, "action": "demarrer"}),
            content_type="application/json",
        ).status_code
        == 302
    )

    client.force_login(autre_proprietaire)
    assert client.get(url_tableau).status_code == 404
    assert client.get(url_etat).status_code == 404
    assert piloter(client, session, "demarrer").status_code == 404


def test_piloter_exige_le_jeton_csrf(proprietaire):
    session = preparer(proprietaire)
    client = Client(enforce_csrf_checks=True)
    client.force_login(proprietaire)
    corps = json.dumps({"code": session.code_session, "action": "demarrer"})

    refus = client.post(
        "/api/piloter/",
        data=corps,
        content_type="application/json",
    )
    assert refus.status_code == 403

    page = client.get(f"/tableau/{session.code_session}/")
    jeton = page.cookies["csrftoken"].value
    accepte = client.post(
        "/api/piloter/",
        data=corps,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=jeton,
    )

    assert accepte.status_code == 200
    assert accepte.json()["statut"] == "en_cours"


def test_tableau_affiche_les_questions_et_le_qr(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    client.force_login(proprietaire)

    attente = client.get(f"/tableau/{session.code_session}/")
    contenu = attente.content.decode()
    assert attente.status_code == 200
    assert session.code_session in contenu
    assert "<svg" in contenu
    assert "Séance en attente" in contenu
    assert "Démarrer" in contenu

    session = demarrer(session)
    table = client.get(f"/tableau/{session.code_session}/")
    contenu = table.content.decode()
    assert table.status_code == 200
    assert "Énoncé très secret E1Q1" in contenu
    assert "Bonne réponse E1Q1" in contenu
    assert "Pause" in contenu
    assert "Suivant" in contenu
    assert "data-question-id" in contenu
    assert "Séance en attente" not in contenu

    donnees = client.get(f"/api/etat_prof/?code={session.code_session}").json()
    assert donnees["ok"] is True
    assert donnees["statut"] == "en_cours"
    assert donnees["nb_etapes"] == 1
    assert donnees["temps_restant_s"] is not None
    assert donnees["questions"][0]["uid"] == "E1Q1"
    assert donnees["questions"][0]["enonce"] == "Énoncé très secret E1Q1"
    assert donnees["questions"][0]["choix"][0]["est_correct"] is True


def test_tableau_termine(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    session = demarrer(session)
    client.force_login(proprietaire)

    from qcm.tests.helpers import expirer_etape

    expirer_etape(session)
    client.get(f"/api/etat_prof/?code={session.code_session}")

    contenu = client.get(f"/tableau/{session.code_session}/").content.decode()
    assert "Séance terminée" in contenu


def test_code_inconnu(client, proprietaire):
    client.force_login(proprietaire)
    assert client.get("/tableau/ZZZZZZ/").status_code == 404
    assert client.get("/rejoindre/ZZZZZZ/").status_code == 404
    assert client.get("/eleve/ZZZZZZ/").status_code == 404

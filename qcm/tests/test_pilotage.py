"""Pilotage professeur : actions, authentification et CSRF."""

import json

import pytest
from django.test import Client

from qcm.import_json import importer_quiz
from qcm.models import Participant, Session
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    piloter,
    rejoindre,
    repondre,
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


def test_terminer_la_seance_est_idempotent(client, proprietaire):
    session = demarrer(preparer(proprietaire))
    client.force_login(proprietaire)

    for _ in range(2):
        reponse = piloter(client, session, "terminer")
        assert reponse.status_code == 200
        assert reponse.json()["statut"] == "fini"

    session.refresh_from_db()
    assert session.statut == Session.STATUT_FINI
    assert session.ends_at is None
    assert session.reste_en_pause is None


def test_terminer_la_seance_refuse_les_reponses_apres_cloture(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    participant = rejoindre(client, session)
    session = demarrer(session)
    question_uid = etat(client, participant["jeton"]).json()["question_uid"]

    client.force_login(proprietaire)
    assert piloter(client, session, "terminer").status_code == 200

    reponse = repondre(client, participant["jeton"], question_uid, ["A"])
    assert reponse.status_code == 409
    assert reponse.json()["raison"] == "seance_non_active"
    assert etat(client, participant["jeton"]).json()["statut"] == "fini"


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


def test_tableau_affiche_les_questions_sans_qr(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    client.force_login(proprietaire)

    attente = client.get(f"/tableau/{session.code_session}/")
    contenu = attente.content.decode()
    assert attente.status_code == 200
    assert session.code_session in contenu
    assert "<svg" not in contenu
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
    assert "Terminer la séance" in contenu
    assert 'data-action="terminer"' in contenu
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


def test_tableau_attente_affiche_le_nombre_de_participants(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    for _ in range(3):
        Participant.objects.create(session=session)
    client.force_login(proprietaire)

    contenu = client.get(f"/tableau/{session.code_session}/").content.decode()

    assert 'class="pied-tableau"' in contenu
    assert 'id="nb-participants">3<' in contenu
    assert 'class="panneau"' not in contenu
    assert 'id="nb-participants-attente"' not in contenu
    donnees = client.get(f"/api/etat_prof/?code={session.code_session}").json()
    assert donnees["nb_participants"] == 3


def test_tableau_termine(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    session = demarrer(session)
    client.force_login(proprietaire)

    expirer_etape(session)
    client.get(f"/api/etat_prof/?code={session.code_session}")

    contenu = client.get(f"/tableau/{session.code_session}/").content.decode()
    assert "Séance terminée" in contenu
    assert "Terminer la séance" in contenu
    assert 'href="/"' in contenu


def test_page_eleve_contient_le_bouton_de_fin(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)

    contenu = client.get(f"/eleve/{session.code_session}/").content.decode()

    assert 'id="fini"' in contenu
    assert "Terminer la séance" in contenu
    assert 'href="/"' in contenu


def test_creation_session_par_le_prof(client, proprietaire, autre_proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1, titre="QCM du prof"), proprietaire)
    client.force_login(proprietaire)

    page = client.get("/session/creer/")
    assert page.status_code == 200
    assert "QCM du prof" in page.content.decode()

    reponse = client.post("/session/creer/", {"quiz": quiz.pk})
    assert reponse.status_code == 302
    session = Session.objects.get(quiz=quiz)
    assert reponse.url == f"/session/{session.code_session}/"

    anonyme = Client()
    assert anonyme.get("/session/creer/").status_code == 302
    assert anonyme.get(f"/session/{session.code_session}/").status_code == 302

    autre = Client()
    autre.force_login(autre_proprietaire)
    assert autre.get(f"/session/{session.code_session}/").status_code == 404
    assert autre.post("/session/creer/", {"quiz": quiz.pk}).status_code == 404


def test_page_initiale_session_affiche_le_qr_et_pas_ailleurs(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    client.force_login(proprietaire)

    page = client.get(f"/session/{session.code_session}/")
    assert page.status_code == 200
    contenu = page.content.decode()
    assert "<svg" in contenu
    assert session.code_session in contenu
    assert f"/tableau/{session.code_session}/" in contenu

    for url in (
        f"/tableau/{session.code_session}/",
        f"/eleve/{session.code_session}/",
        f"/rejoindre/{session.code_session}/",
        "/",
    ):
        assert "<svg" not in client.get(url).content.decode()


def test_code_inconnu(client, proprietaire):
    client.force_login(proprietaire)
    assert client.get("/tableau/ZZZZZZ/").status_code == 404
    assert client.get("/rejoindre/ZZZZZZ/").status_code == 404
    assert client.get("/eleve/ZZZZZZ/").status_code == 404

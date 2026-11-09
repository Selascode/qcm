"""Page participants et endpoint de polling (V2)."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from qcm.import_json import importer_quiz
from qcm.models import Participant, Session
from qcm.tests.helpers import (
    creer_eleve,
    donnees_quiz,
    etat_participants,
    rejoindre_eleve,
)

pytestmark = pytest.mark.django_db

CLES_INTERDITES = {"pin", "pin_hash", "enonce", "texte", "est_correct"}


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


def _connexion(client, session, code="MD0001", pin="123456"):
    return rejoindre_eleve(client, session, code, pin)


def test_page_participants_liste_le_groupe_complet(
    client, proprietaire, groupe, session_groupe
):
    creer_eleve(groupe, nom="Dupont", prenom="Marie", code_etudiant="MD0001")
    creer_eleve(groupe, nom="Martin", prenom="Paul", code_etudiant="PM0002")
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:participants", args=[session_groupe.code_session])
    )

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "Dupont" in contenu
    assert "Marie" in contenu
    assert "MD0001" in contenu
    assert "Martin" in contenu
    assert "0 / 2" in contenu
    assert "123456" not in contenu
    assert "pin_hash" not in contenu


def test_page_participants_refusee_a_un_autre_professeur(
    client, proprietaire, autre_proprietaire, groupe, session_groupe
):
    client.force_login(autre_proprietaire)

    reponse = client.get(
        reverse("qcm:participants", args=[session_groupe.code_session])
    )

    assert reponse.status_code == 403


def test_page_participants_anonyme_redirige(client, groupe, session_groupe):
    reponse = client.get(
        reverse("qcm:participants", args=[session_groupe.code_session])
    )

    assert reponse.status_code == 302


def test_page_participants_groupe_null(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = Session.objects.create(quiz=quiz)
    client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session.code_session}),
        content_type="application/json",
    )
    client.force_login(proprietaire)

    reponse = client.get(reverse("qcm:participants", args=[session.code_session]))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "aucun groupe" in contenu
    assert "participants apparaîtront à la connexion" in contenu


def test_etat_participants_passe_au_vert_apres_connexion(
    client, proprietaire, groupe, session_groupe
):
    creer_eleve(groupe, nom="Dupont", prenom="Marie", code_etudiant="MD0001")
    creer_eleve(groupe, nom="Martin", prenom="Paul", code_etudiant="PM0002")
    client.force_login(proprietaire)

    avant = etat_participants(client, session_groupe).json()
    assert avant["connectes"] == 0
    assert avant["total"] == 2
    assert all(not ligne["connecte"] for ligne in avant["participants"])

    _connexion(client, session_groupe)
    apres = etat_participants(client, session_groupe).json()

    marie = next(
        ligne for ligne in apres["participants"] if ligne["code_etudiant"] == "MD0001"
    )
    paul = next(
        ligne for ligne in apres["participants"] if ligne["code_etudiant"] == "PM0002"
    )
    assert marie["connecte"] is True
    assert marie["derniere_activite_s"] is not None
    assert paul["connecte"] is False
    assert apres["connectes"] == 1


def test_statut_connecte_est_irreversible(
    client, proprietaire, groupe, session_groupe
):
    creer_eleve(groupe, code_etudiant="MD0001")
    _connexion(client, session_groupe)
    client.force_login(proprietaire)
    Participant.objects.update(
        derniere_activite=timezone.now() - timedelta(hours=1)
    )

    donnees = etat_participants(client, session_groupe).json()

    assert donnees["participants"][0]["connecte"] is True
    assert donnees["participants"][0]["derniere_activite_s"] >= 3000


def test_etat_participants_refuse_a_un_autre_professeur(
    client, autre_proprietaire, groupe, session_groupe
):
    client.force_login(autre_proprietaire)

    assert etat_participants(client, session_groupe).status_code == 403


def test_etat_participants_sans_fuite(client, proprietaire, groupe, session_groupe):
    creer_eleve(groupe, code_etudiant="MD0001", pin="123456")
    _connexion(client, session_groupe)
    client.force_login(proprietaire)

    reponse = etat_participants(client, session_groupe)
    contenu = reponse.content.decode()
    donnees = reponse.json()

    verifier_cles(donnees)
    for interdit in ("pin_hash", "enonce", "est_correct"):
        assert interdit not in contenu
    assert "123456" not in contenu


def test_reinitialiser_l_appareil(
    client, proprietaire, groupe, session_groupe
):
    creer_eleve(groupe, code_etudiant="MD0001")
    jeton_initial = _connexion(client, session_groupe).json()["jeton"]
    participant = Participant.objects.get(session=session_groupe)
    client.force_login(proprietaire)

    reponse = client.post(
        reverse(
            "qcm:reinitialiser_appareil",
            args=[session_groupe.code_session, participant.pk],
        )
    )

    assert reponse.status_code == 302
    participant.refresh_from_db()
    assert str(participant.jeton_appareil) != jeton_initial


def test_reinitialiser_refuse_a_un_autre_professeur(
    client, proprietaire, autre_proprietaire, groupe, session_groupe
):
    creer_eleve(groupe, code_etudiant="MD0001")
    _connexion(client, session_groupe)
    participant = Participant.objects.get(session=session_groupe)
    client.force_login(autre_proprietaire)

    reponse = client.post(
        reverse(
            "qcm:reinitialiser_appareil",
            args=[session_groupe.code_session, participant.pk],
        )
    )

    assert reponse.status_code == 403


def test_liens_participants_et_resultats_depuis_la_seance(
    client, proprietaire, groupe, session_groupe
):
    client.force_login(proprietaire)

    initiale = client.get(
        reverse("qcm:session_initiale", args=[session_groupe.code_session])
    )
    tableau = client.get(
        reverse("qcm:tableau", args=[session_groupe.code_session])
    )

    for page in (initiale, tableau):
        contenu = page.content.decode()
        assert f"/session/{session_groupe.code_session}/participants/" in contenu
        assert f"/resultats/{session_groupe.code_session}/" in contenu

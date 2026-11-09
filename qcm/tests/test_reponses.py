"""POST /api/repondre/ : acceptation, refus tardif, doublons et validation."""

import json
import uuid

import pytest

from qcm.import_json import importer_quiz
from qcm.models import Answer
from qcm.services import etape_precedente, etape_suivante, mettre_en_pause
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    rejoindre,
    repondre,
)

pytestmark = pytest.mark.django_db


def preparer(client, proprietaire, questions_par_etape=1):
    quiz = importer_quiz(donnees_quiz(1, questions_par_etape, duree_s=60), proprietaire)
    session = creer_session(quiz)
    demarrer(session)
    participant = rejoindre(client, session)
    donnees = etat(client, participant["jeton"]).json()
    return session, participant, donnees


def test_reponse_acceptee_avant_la_fin(client, proprietaire):
    session, participant, donnees = preparer(client, proprietaire)

    reponse = repondre(
        client,
        participant["jeton"],
        donnees["question_uid"],
        ["A", "B"],
    )

    assert reponse.status_code == 200
    body = reponse.json()
    assert body["ok"] is True
    assert body["recu"] is True
    assert body["id_client"]
    assert "enonce" not in body
    assert Answer.objects.count() == 1
    answer = Answer.objects.get()
    assert answer.session_id == session.pk
    assert answer.participant_id == participant["participant_id"]
    assert answer.choix_selectionnes == ["A", "B"]
    assert answer.source == Answer.SOURCE_APP


def test_reponse_apres_ends_at_refusee(client, proprietaire):
    session, participant, donnees = preparer(client, proprietaire)
    expirer_etape(session)

    reponse = repondre(
        client,
        participant["jeton"],
        donnees["question_uid"],
        ["A"],
    )

    assert reponse.status_code == 409
    assert reponse.json()["raison"] == "temps_ecoule"
    assert Answer.objects.count() == 0


def test_seconde_reponse_a_la_meme_question_refusee(client, proprietaire):
    _, participant, donnees = preparer(client, proprietaire)
    premier = repondre(client, participant["jeton"], donnees["question_uid"], ["A"])
    assert premier.status_code == 200

    seconde = repondre(client, participant["jeton"], donnees["question_uid"], ["B"])

    assert seconde.status_code == 409
    assert seconde.json()["raison"] == "deja_repondu"
    assert Answer.objects.count() == 1


def test_meme_id_client_est_idempotent(client, proprietaire):
    _, participant, donnees = preparer(client, proprietaire)
    id_client = str(uuid.uuid4())

    premier = repondre(
        client,
        participant["jeton"],
        donnees["question_uid"],
        ["A"],
        id_client=id_client,
    )
    second = repondre(
        client,
        participant["jeton"],
        donnees["question_uid"],
        ["B"],
        id_client=id_client,
    )

    assert premier.status_code == 200
    assert second.status_code == 200
    assert second.json()["deja"] is True
    assert Answer.objects.count() == 1
    assert Answer.objects.get().choix_selectionnes == ["A"]


@pytest.mark.parametrize("choix", [[], ["Z"], ["A", "A"]])
def test_choix_invalides_refuses(client, proprietaire, choix):
    _, participant, donnees = preparer(client, proprietaire)

    reponse = repondre(client, participant["jeton"], donnees["question_uid"], choix)

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "choix_invalide"
    assert Answer.objects.count() == 0


def test_question_d_une_autre_couleur_refusee(client, proprietaire):
    _, participant, donnees = preparer(client, proprietaire, questions_par_etape=2)
    autre = "E1Q2" if donnees["question_uid"] == "E1Q1" else "E1Q1"

    reponse = repondre(client, participant["jeton"], autre, ["A"])

    assert reponse.status_code == 409
    assert reponse.json()["raison"] == "mauvaise_question"
    assert Answer.objects.count() == 0


def test_question_inconnue(client, proprietaire):
    _, participant, _ = preparer(client, proprietaire)

    reponse = repondre(client, participant["jeton"], "INCONNUE", ["A"])

    assert reponse.status_code == 404
    assert reponse.json()["raison"] == "question_inconnue"


def test_reponse_pendant_une_pause_refusee(client, proprietaire):
    session, participant, donnees = preparer(client, proprietaire)
    mettre_en_pause(session)

    reponse = repondre(client, participant["jeton"], donnees["question_uid"], ["A"])

    assert reponse.status_code == 409
    assert reponse.json()["raison"] == "seance_non_active"


def test_reponse_apres_la_fin_refusee(client, proprietaire):
    session, participant, donnees = preparer(client, proprietaire)
    expirer_etape(session)
    assert etat(client, participant["jeton"]).json()["statut"] == "fini"

    reponse = repondre(client, participant["jeton"], donnees["question_uid"], ["A"])

    assert reponse.status_code == 409
    assert reponse.json()["raison"] == "seance_non_active"


def test_jeton_invalide_refuse(client, proprietaire):
    _, _, donnees = preparer(client, proprietaire)

    reponse = client.post(
        "/api/repondre/",
        data=json.dumps(
            {
                "id_client": str(uuid.uuid4()),
                "question_uid": donnees["question_uid"],
                "choix": ["A"],
            }
        ),
        content_type="application/json",
    )

    assert reponse.status_code == 401


def test_json_invalide_refuse(client, proprietaire):
    _, participant, _ = preparer(client, proprietaire)

    reponse = client.post(
        "/api/repondre/",
        data="{",
        content_type="application/json",
        headers={"X-Jeton": participant["jeton"]},
    )

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "json_invalide"


def test_id_client_invalide_refuse(client, proprietaire):
    _, participant, donnees = preparer(client, proprietaire)

    reponse = client.post(
        "/api/repondre/",
        data=json.dumps(
            {
                "id_client": "pas-un-uuid",
                "question_uid": donnees["question_uid"],
                "choix": ["A"],
            }
        ),
        content_type="application/json",
        headers={"X-Jeton": participant["jeton"]},
    )

    assert reponse.status_code == 400
    assert reponse.json()["raison"] == "id_client_invalide"


def test_une_reponse_par_question_meme_apres_retour(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(2, 1, duree_s=60), proprietaire)
    session = creer_session(quiz)
    demarrer(session)
    participant = rejoindre(client, session)
    donnees = etat(client, participant["jeton"]).json()
    assert (
        repondre(
            client, participant["jeton"], donnees["question_uid"], ["A"]
        ).status_code
        == 200
    )

    session = etape_suivante(session)
    assert session.etape_courante == 2
    session = etape_precedente(session)
    assert session.etape_courante == 1

    seconde = repondre(client, participant["jeton"], donnees["question_uid"], ["B"])

    assert seconde.status_code == 409
    assert seconde.json()["raison"] == "deja_repondu"

"""Aucune fuite d'énoncé, de texte de choix ou de correction vers l'élève."""

import json

import pytest

from qcm.import_questions import importer_quiz
from qcm.services import mettre_en_pause, reprendre
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    repondre,
)

pytestmark = pytest.mark.django_db

CLES_INTERDITES = {"enonce", "texte", "est_correct"}


def verifier_cles(valeur) -> None:
    if isinstance(valeur, dict):
        for cle, sous_valeur in valeur.items():
            assert cle not in CLES_INTERDITES, f"clé interdite : {cle}"
            verifier_cles(sous_valeur)
    elif isinstance(valeur, list):
        for sous_valeur in valeur:
            verifier_cles(sous_valeur)


def textes_du_quiz(quiz) -> list[str]:
    textes = []
    for question in quiz.questions.all():
        textes.append(question.enonce)
        textes.extend(choix.texte for choix in question.choices.all())
    return textes


def verifier_textes(contenu: str, textes: list[str]) -> None:
    for texte in textes:
        assert texte not in contenu, f"fuite de « {texte} »"


def verifier_reponse(reponse, textes: list[str]) -> None:
    contenu = reponse.content.decode()
    verifier_textes(contenu, textes)
    if reponse.headers.get("Content-Type", "").startswith("application/json"):
        donnees = reponse.json()
        verifier_cles(donnees)
        verifier_textes(json.dumps(donnees, ensure_ascii=False), textes)


def test_aucune_fuite_dans_les_endpoints_eleves(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(2, 1), proprietaire)
    session = creer_session(quiz)
    textes = textes_du_quiz(quiz)
    reponses_a_verifier = []

    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session.code_session}),
        content_type="application/json",
    )
    participant = reponse.json()
    reponses_a_verifier.append(reponse)

    reponses_a_verifier.append(etat(client, participant["jeton"]))
    session = demarrer(session)
    reponses_a_verifier.append(etat(client, participant["jeton"]))
    question_uid = reponses_a_verifier[-1].json()["question_uid"]

    reponses_a_verifier.append(
        repondre(client, participant["jeton"], question_uid, ["A"])
    )
    reponses_a_verifier.append(etat(client, participant["jeton"]))
    reponses_a_verifier.append(
        repondre(client, participant["jeton"], question_uid, ["B"])
    )

    session = mettre_en_pause(session)
    reponses_a_verifier.append(etat(client, participant["jeton"]))

    session = reprendre(session)
    expirer_etape(session)
    reponses_a_verifier.append(etat(client, participant["jeton"]))
    reponses_a_verifier.append(etat(client, participant["jeton"]))

    reponses_a_verifier.append(
        client.get("/api/etat/", headers={"X-Jeton": "pas-un-jeton"})
    )
    reponses_a_verifier.append(
        client.post(
            "/api/repondre/",
            data="{",
            content_type="application/json",
            headers={"X-Jeton": participant["jeton"]},
        )
    )

    for reponse in reponses_a_verifier:
        verifier_reponse(reponse, textes)

    for url in (
        f"/rejoindre/{session.code_session}/",
        f"/eleve/{session.code_session}/",
    ):
        verifier_textes(client.get(url).content.decode(), textes)


def test_aucune_fuite_dans_les_pages_eleves(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    textes = textes_du_quiz(quiz)

    for url in (
        "/rejoindre/",
        f"/rejoindre/{session.code_session}/",
        f"/eleve/{session.code_session}/",
    ):
        reponse = client.get(url)
        assert reponse.status_code == 200
        verifier_textes(reponse.content.decode(), textes)

"""Exports CSV des résultats : UTF-8 BOM, virgule, note /20."""

import codecs
import csv
import io
import uuid

import pytest
from django.urls import reverse

from qcm.import_questions import importer_quiz
from qcm.models import Answer, Participant, Session
from qcm.tests.helpers import creer_eleve

pytestmark = pytest.mark.django_db


def _donnees() -> dict:
    return {
        "titre": "Exports",
        "questions": [
            {
                "uid": "Q1",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Question 1",
                "type": "unique",
                "choix": [
                    {"lettre": "A", "texte": "bonne", "correct": True},
                    {"lettre": "B", "texte": "mauvaise", "correct": False},
                ],
            },
            {
                "uid": "Q2",
                "etape": 1,
                "duree_s": 60,
                "enonce": "Question 2",
                "type": "multiple",
                "choix": [
                    {"lettre": "A", "texte": "bonne 1", "correct": True},
                    {"lettre": "B", "texte": "bonne 2", "correct": True},
                    {"lettre": "C", "texte": "mauvaise", "correct": False},
                ],
            },
        ],
    }


def _preparer(proprietaire, groupe):
    quiz = importer_quiz(_donnees(), proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    marie = creer_eleve(
        groupe,
        nom="Dupont",
        prenom="Marie",
        code_etudiant="MD0001",
        identifiant_insa="INS-MARIE",
    )
    paul = creer_eleve(
        groupe,
        nom="Martin",
        prenom="Paul",
        code_etudiant="PM0002",
    )
    participant_marie = Participant.objects.create(session=session, student=marie)
    participant_paul = Participant.objects.create(session=session, student=paul)
    questions = {question.uid: question for question in quiz.questions.all()}
    Answer.objects.create(
        session=session,
        participant=participant_marie,
        question=questions["Q1"],
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_marie,
        question=questions["Q2"],
        choix_selectionnes=["A"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_paul,
        question=questions["Q1"],
        choix_selectionnes=["B"],
        id_client=uuid.uuid4(),
    )
    Answer.objects.create(
        session=session,
        participant=participant_paul,
        question=questions["Q2"],
        choix_selectionnes=["A", "B"],
        id_client=uuid.uuid4(),
    )
    return session


def _lignes(reponse) -> list[list[str]]:
    contenu = reponse.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(contenu)))


def test_export_notes_bom_entete_et_note_sur_20(
    client, proprietaire, groupe
):
    session = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:exporter_resultats_notes", args=[session.code_session])
    )

    assert reponse.status_code == 200
    assert reponse.content.startswith(codecs.BOM_UTF8)
    assert reponse["Content-Type"].startswith("text/csv")
    contenu = reponse.content.decode("utf-8-sig")
    assert contenu.splitlines()[0] == (
        "Nom,Prénom,Identifiant,Note /20,Q1,Q2"
    )

    lignes = _lignes(reponse)
    par_prenom = {ligne[1]: ligne for ligne in lignes[1:]}
    assert par_prenom["Marie"] == [
        "Dupont",
        "Marie",
        "INS-MARIE",
        "15.00",
        "A",
        "A",
    ]
    assert par_prenom["Paul"] == [
        "Martin",
        "Paul",
        "PM0002",
        "0.00",
        "B",
        "AB",
    ]


def test_export_detail_entete_bom_et_points(client, proprietaire, groupe):
    session = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:exporter_resultats_detail", args=[session.code_session])
    )

    assert reponse.status_code == 200
    assert reponse.content.startswith(codecs.BOM_UTF8)
    lignes = _lignes(reponse)
    assert lignes[0] == [
        "Nom",
        "Prénom",
        "Identifiant",
        "Question",
        "Réponse donnée",
        "Bonne réponse",
        "Points obtenus",
    ]

    par_cle = {
        (ligne[1], ligne[3].split(" — ")[0]): ligne
        for ligne in lignes[1:]
    }
    marie_q1 = par_cle[("Marie", "Q1")]
    assert marie_q1[:3] == ["Dupont", "Marie", "INS-MARIE"]
    assert marie_q1[3] == "Q1 — Question 1"
    assert marie_q1[4:] == ["A", "A", "1.00"]

    marie_q2 = par_cle[("Marie", "Q2")]
    assert marie_q2[4:] == ["A", "AB", "0.50"]

    paul_q1 = par_cle[("Paul", "Q1")]
    assert paul_q1[4:] == ["B", "A", "-1.00"]


def test_exports_refuses_a_un_autre_professeur(
    client, proprietaire, groupe, autre_proprietaire
):
    session = _preparer(proprietaire, groupe)
    client.force_login(autre_proprietaire)

    for nom in ("exporter_resultats_notes", "exporter_resultats_detail"):
        reponse = client.get(
            reverse(f"qcm:{nom}", args=[session.code_session])
        )
        assert reponse.status_code == 403


def test_exports_anonymes_redirigent(client, proprietaire, groupe):
    session = _preparer(proprietaire, groupe)

    for nom in ("exporter_resultats_notes", "exporter_resultats_detail"):
        reponse = client.get(
            reverse(f"qcm:{nom}", args=[session.code_session])
        )
        assert reponse.status_code == 302

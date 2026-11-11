"""Critère V1 : 5 paquets (20 étapes), redémarrage serveur au milieu, zéro perte."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client

from qcm.import_json import importer_quiz
from qcm.models import Answer, Participant, Session
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    rejoindre,
    repondre,
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_parcours_vingt_etapes_avec_redemarrage(client):
    proprietaire = get_user_model().objects.create_user(
        username="prof-parcours",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(5, 4, duree_s=90), proprietaire)
    session = creer_session(quiz)
    jetons = []
    for couleur in (1, 2, 3, 4):
        donnees = rejoindre(client, session)
        Participant.objects.filter(pk=donnees["participant_id"]).update(
            couleur_assignee=couleur
        )
        jetons.append((donnees["jeton"], donnees["participant_id"]))
    session = demarrer(session)

    for etape in range(1, 21):
        for jeton, _ in jetons:
            donnees = etat(client, jeton).json()
            assert donnees["statut"] == "en_cours"
            assert donnees["etape"] == etape
            assert donnees["question_uid"] is not None
            assert donnees["lettres"]
            reponse = repondre(
                client,
                jeton,
                donnees["question_uid"],
                [donnees["lettres"][0]],
                id_client=uuid.uuid4(),
            )
            assert reponse.status_code == 200, reponse.content

        if etape == 2:
            connections.close_all()
            client = Client()

        expirer_etape(session)
        donnees = etat(client, jetons[0][0]).json()
        if etape < 20:
            assert donnees["statut"] == "en_cours"
            assert donnees["etape"] == etape + 1
        else:
            assert donnees["statut"] == "fini"

    session = Session.objects.get(pk=session.pk)
    assert session.statut == Session.STATUT_FINI
    assert Answer.objects.count() == 80
    assert Answer.objects.values("question_id").distinct().count() == 20
    for _, participant_id in jetons:
        assert Answer.objects.filter(participant_id=participant_id).count() == 20

    # Reconnexion d'un élève après le redémarrage : ses réponses sont là.
    donnees = etat(client, jetons[0][0]).json()
    assert donnees["statut"] == "fini"
    assert donnees["deja_repondu"] is False

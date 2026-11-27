"""Test de charge V4 : 100 clients simultanés, zéro réponse perdue."""

import pytest

from qcm.import_questions import importer_quiz
from qcm.models import Answer
from qcm.tests.helpers import (
    creer_eleve,
    creer_groupe,
    creer_session,
    demarrer,
    donnees_quiz,
)
from scripts.test_charge import executer_charge

pytestmark = pytest.mark.django_db(transaction=True)


def test_cent_clients_ne_perdent_aucune_reponse(live_server, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1, duree_s=300), proprietaire)
    groupe = creer_groupe(proprietaire, nom="Charge 100")
    session = creer_session(quiz)
    session.groupe = groupe
    session.save(update_fields=["groupe"])

    identifiants = []
    for index in range(100):
        eleve = creer_eleve(
            groupe,
            nom=f"Nom{index:03d}",
            prenom="Élève",
            code_etudiant=f"CH{index:04d}",
        )
        identifiants.append(eleve.code_etudiant)

    demarrer(session)
    resultat = executer_charge(
        live_server.url,
        session.code_session,
        identifiants,
        nb_clients=100,
        timeout=20,
    )

    echecs = [resultat for resultat in resultat.resultats if not resultat.ok]
    assert resultat.echecs == 0, echecs[:5]
    assert resultat.succes == 100
    assert resultat.temps_moyen_reponse_s is not None
    assert resultat.temps_moyen_reponse_s > 0
    assert Answer.objects.filter(session=session).count() == 100

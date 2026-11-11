"""Horloge serveur : démarrage, auto-avance, pause, reprise et +temps."""

from datetime import timedelta

import pytest
from django.utils import timezone

from qcm import services
from qcm.import_questions import importer_quiz
from qcm.models import Session
from qcm.tests.helpers import (
    creer_session,
    demarrer,
    donnees_quiz,
    etat,
    expirer_etape,
    rejoindre,
)

pytestmark = pytest.mark.django_db


def construire(proprietaire, nb_etapes=5, questions_par_etape=1, duree_s=60):
    quiz = importer_quiz(
        donnees_quiz(nb_etapes, questions_par_etape, duree_s=duree_s),
        proprietaire,
    )
    return creer_session(quiz)


def test_demarrage_pose_ends_at_serveur(proprietaire):
    session = construire(proprietaire)
    avant = timezone.now()

    session = demarrer(session)

    apres = timezone.now()
    assert session.statut == Session.STATUT_EN_COURS
    assert session.etape_courante == 1
    assert avant + timedelta(seconds=60) <= session.ends_at
    assert session.ends_at <= apres + timedelta(seconds=61)
    assert 59 <= services.temps_restant_s(session) <= 60


def test_auto_avance_une_seule_etape_a_la_fois(proprietaire):
    session = demarrer(construire(proprietaire, nb_etapes=5))
    expirer_etape(session)

    session = services.avancer_si_necessaire(session)

    assert session.etape_courante == 2
    assert session.statut == Session.STATUT_EN_COURS
    assert services.temps_restant_s(session) >= 55

    session = services.avancer_si_necessaire(session)
    assert session.etape_courante == 2


def test_auto_avance_jusqu_a_la_fin(proprietaire):
    session = demarrer(construire(proprietaire, nb_etapes=2))
    expirer_etape(session)
    session = services.avancer_si_necessaire(session)
    assert session.etape_courante == 2

    expirer_etape(session)
    session = services.avancer_si_necessaire(session)

    assert session.statut == Session.STATUT_FINI
    assert session.ends_at is None
    assert session.reste_en_pause is None


def test_auto_avance_via_api_eleve(client, proprietaire):
    session = construire(proprietaire, nb_etapes=2)
    participant = rejoindre(client, session)
    session = demarrer(session)

    assert etat(client, participant["jeton"]).json()["etape"] == 1

    expirer_etape(session)
    donnees = etat(client, participant["jeton"]).json()
    assert donnees["etape"] == 2
    assert donnees["statut"] == "en_cours"

    expirer_etape(session)
    donnees = etat(client, participant["jeton"]).json()
    assert donnees["statut"] == "fini"


def test_pause_reprise_et_temps_ajoute(proprietaire):
    session = demarrer(construire(proprietaire))

    session = services.mettre_en_pause(session)
    assert session.statut == Session.STATUT_PAUSE
    assert session.ends_at is None
    assert 55 <= session.reste_en_pause <= 60
    reste = session.reste_en_pause

    session = services.ajouter_temps(session, 30)
    assert session.reste_en_pause == reste + 30

    session = services.reprendre(session)
    assert session.statut == Session.STATUT_EN_COURS
    assert session.reste_en_pause is None
    restant = (session.ends_at - timezone.now()).total_seconds()
    assert reste + 30 - 2 <= restant <= reste + 30 + 2

    avant = session.ends_at
    session = services.ajouter_temps(session, 60)
    assert (session.ends_at - avant).total_seconds() == 60


@pytest.mark.parametrize("secondes", [0, -1, 3601, "60", True])
def test_ajout_de_temps_invalide(proprietaire, secondes):
    session = demarrer(construire(proprietaire))

    with pytest.raises(services.ErreurPilotage):
        services.ajouter_temps(session, secondes)


def test_suivant_et_precedent(proprietaire):
    session = demarrer(construire(proprietaire, nb_etapes=3))

    session = services.etape_suivante(session)
    assert session.etape_courante == 2

    session = services.etape_precedente(session)
    assert session.etape_courante == 1

    with pytest.raises(services.ErreurPilotage):
        services.etape_precedente(session)


def test_suivant_depuis_une_pause_reprend(proprietaire):
    session = demarrer(construire(proprietaire, nb_etapes=2))
    session = services.mettre_en_pause(session)

    session = services.etape_suivante(session)

    assert session.statut == Session.STATUT_EN_COURS
    assert session.etape_courante == 2


def test_suivant_depuis_la_derniere_etape_termine(proprietaire):
    session = demarrer(construire(proprietaire, nb_etapes=2))
    session = services.etape_suivante(session)
    session = services.etape_suivante(session)

    assert session.statut == Session.STATUT_FINI
    assert session.ends_at is None


def test_pilotage_refuse_dans_le_mauvais_etat(proprietaire):
    session = construire(proprietaire)

    for action in (
        services.mettre_en_pause,
        services.reprendre,
        services.etape_suivante,
        services.etape_precedente,
    ):
        with pytest.raises(services.ErreurPilotage):
            action(session)

    session = demarrer(session)
    with pytest.raises(services.ErreurPilotage):
        services.demarrer_session(session)

    session = services.mettre_en_pause(session)
    with pytest.raises(services.ErreurPilotage):
        services.mettre_en_pause(session)


def test_equation_du_temps_restant_suit_ends_at(proprietaire):
    session = demarrer(construire(proprietaire, duree_s=120))

    assert services.temps_restant_s(session) > 100

    Session.objects.filter(pk=session.pk).update(
        ends_at=timezone.now() + timedelta(seconds=10)
    )
    session.refresh_from_db()
    assert 9 <= services.temps_restant_s(session) <= 10

    Session.objects.filter(pk=session.pk).update(
        ends_at=timezone.now() - timedelta(seconds=10)
    )
    session.refresh_from_db()
    assert services.temps_restant_s(session) == 0

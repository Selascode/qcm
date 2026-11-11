"""URL du QR code configurable via ``QCM_LAN_HOST`` (suivi PR #6)."""

import pytest
from django.test import override_settings
from django.urls import reverse

from qcm.import_json import importer_quiz
from qcm.tests.helpers import creer_session, donnees_quiz

pytestmark = pytest.mark.django_db


def _session(proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    return creer_session(quiz)


@override_settings(QCM_LAN_HOST="")
def test_url_qr_sans_hote_configure_utilise_la_requete(client, proprietaire):
    session = _session(proprietaire)
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:session_initiale", args=[session.code_session])
    )

    assert reponse.status_code == 200
    assert reponse.context["url_rejoindre"] == (
        f"http://testserver/rejoindre/{session.code_session}/"
    )


@override_settings(QCM_LAN_HOST="192.168.1.42:8000")
def test_url_qr_avec_hote_configure(client, proprietaire):
    session = _session(proprietaire)
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:session_initiale", args=[session.code_session])
    )

    assert reponse.status_code == 200
    assert reponse.context["url_rejoindre"] == (
        f"http://192.168.1.42:8000/rejoindre/{session.code_session}/"
    )
    assert "URL encodée" in reponse.content.decode()


@override_settings(QCM_LAN_HOST="")
def test_url_qr_hote_vide_ne_plante_pas(client, proprietaire):
    session = _session(proprietaire)
    client.force_login(proprietaire)

    reponse = client.get(
        reverse("qcm:session_initiale", args=[session.code_session])
    )

    assert reponse.status_code == 200
    assert reponse.context["url_rejoindre"].startswith("http://testserver/")


def test_page_initiale_refusee_a_un_autre_professeur(
    client, proprietaire, autre_proprietaire
):
    session = _session(proprietaire)
    client.force_login(autre_proprietaire)

    reponse = client.get(
        reverse("qcm:session_initiale", args=[session.code_session])
    )

    assert reponse.status_code == 403


@override_settings(QCM_LAN_HOST="192.168.1.42:8000")
def test_tableau_attente_affiche_qr_et_code(client, proprietaire):
    session = _session(proprietaire)
    client.force_login(proprietaire)

    reponse = client.get(reverse("qcm:tableau", args=[session.code_session]))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert session.code_session in contenu
    assert "<svg" in contenu
    assert "URL encodée" in contenu
    assert reponse.context["url_rejoindre"] == (
        f"http://192.168.1.42:8000/rejoindre/{session.code_session}/"
    )
    assert reponse.context["qr_svg"]

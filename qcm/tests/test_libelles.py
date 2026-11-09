"""Libellés français dans les modèles et dans les pages rendues."""

import pytest
from django.contrib.auth import get_user_model

from qcm.import_json import importer_quiz
from qcm.models import Answer, Choice, Participant, Question, Quiz, Session, Step
from qcm.tests.helpers import creer_session, donnees_quiz

pytestmark = pytest.mark.django_db

LIBELLES_ANGLAIS = (
    "Answers",
    "Choices",
    "Participants",
    "Quizzes",
    "Sessions",
    "Steps",
)

MODELES = (
    (Quiz, "QCM", "QCM"),
    (Step, "Étape", "Étapes"),
    (Question, "Question", "Questions"),
    (Choice, "Choix", "Choix"),
    (Session, "Séance", "Séances"),
    (Participant, "Élève", "Élèves"),
    (Answer, "Réponse", "Réponses"),
)


@pytest.mark.parametrize("modele,singulier,pluriel", MODELES)
def test_verbose_names_en_francais(modele, singulier, pluriel):
    assert modele._meta.verbose_name == singulier
    assert modele._meta.verbose_name_plural == pluriel


def test_aucun_libelle_anglais_dans_les_pages_rendues(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-libelles",
        email="admin-libelles@example.com",
        password="secret",
    )
    quiz = importer_quiz(
        donnees_quiz(1, 1, titre="QCM de test"),
        administrateur,
    )
    session = creer_session(quiz)
    Participant.objects.create(session=session)
    client.force_login(administrateur)

    urls = (
        "/",
        "/rejoindre/",
        f"/rejoindre/{session.code_session}/",
        f"/eleve/{session.code_session}/",
        f"/tableau/{session.code_session}/",
        "/session/creer/",
        f"/session/{session.code_session}/",
        "/admin/",
        "/admin/qcm/answer/",
        "/admin/qcm/choice/",
        "/admin/qcm/participant/",
        "/admin/qcm/question/",
        "/admin/qcm/quiz/",
        "/admin/qcm/session/",
        "/admin/qcm/step/",
    )

    for url in urls:
        reponse = client.get(url)
        assert reponse.status_code == 200, url
        contenu = reponse.content.decode()
        for libelle in LIBELLES_ANGLAIS:
            assert libelle not in contenu, f"{libelle} visible dans {url}"

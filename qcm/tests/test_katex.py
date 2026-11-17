"""KaTeX doit être servi localement pour fonctionner sans Internet (V4)."""

import pytest
from django.contrib.staticfiles import finders

from qcm.import_questions import importer_quiz
from qcm.tests.helpers import creer_session, demarrer, donnees_quiz

pytestmark = pytest.mark.django_db


def test_katex_est_servi_localement_sans_cdn(client, proprietaire):
    quiz = importer_quiz(donnees_quiz(1, 1), proprietaire)
    session = creer_session(quiz)
    demarrer(session)
    client.force_login(proprietaire)

    for url in (
        f"/tableau/{session.code_session}/",
        f"/tableau/{session.code_session}/presentation/",
    ):
        contenu = client.get(url).content.decode()
        assert "qcm/katex/katex.min.css" in contenu
        assert "qcm/katex/katex.min.js" in contenu
        assert "qcm/katex/contrib/auto-render.min.js" in contenu
        assert "cdn.jsdelivr.net" not in contenu

    for chemin in (
        "qcm/katex/katex.min.css",
        "qcm/katex/katex.min.js",
        "qcm/katex/contrib/auto-render.min.js",
        "qcm/katex/fonts/KaTeX_Main-Regular.woff2",
    ):
        assert finders.find(chemin) is not None, chemin

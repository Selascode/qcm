"""Saisie papier groupée, liaison rapide et import CSV des réponses papier."""

import uuid
from html import unescape

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from qcm.import_questions import importer_quiz
from qcm.models import Answer, Groupe, Participant, Session
from qcm.tests.helpers import creer_eleve, donnees_quiz

pytestmark = pytest.mark.django_db


def _url(session: Session) -> str:
    return reverse("qcm:saisie_papier", args=[session.code_session])


def _preparer(proprietaire, groupe):
    quiz = importer_quiz(donnees_quiz(2, 1), proprietaire)
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    marie = creer_eleve(
        groupe,
        nom="Dupont",
        prenom="Marie",
        code_etudiant="MARIE-DUP00",
    )
    paul = creer_eleve(
        groupe,
        nom="Martin",
        prenom="Paul",
        code_etudiant="PAUL-MAR00",
    )
    questions = {question.uid: question for question in quiz.questions.all()}
    return session, marie, paul, questions


def _texte(reponse) -> str:
    return unescape(reponse.content.decode())


def _fichier_csv(contenu: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "reponses.csv",
        contenu.encode("utf-8-sig"),
        content_type="text/csv",
    )


def test_page_saisie_papier_accessible_au_proprietaire(
    client, proprietaire, groupe
):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.get(_url(session))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "Saisie papier" in contenu
    assert "Choisir un élève" in contenu
    assert "MARIE-DUP00" in contenu
    assert "PAUL-MAR00" in contenu
    assert "sans participant" in contenu
    assert "Importer des réponses papier (CSV)" in contenu


def test_page_saisie_papier_refusee_a_un_autre_professeur(
    client, proprietaire, groupe, autre_proprietaire
):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(autre_proprietaire)

    assert client.get(_url(session)).status_code == 403


def test_page_saisie_papier_anonyme_redirige(client, proprietaire, groupe):
    session, _, _, _ = _preparer(proprietaire, groupe)

    assert client.get(_url(session)).status_code == 302


def test_formulaire_affiche_les_questions_et_les_choix(
    client, proprietaire, groupe
):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    contenu = client.get(f"{_url(session)}?eleve={marie.pk}").content.decode()

    assert "E1Q1" in contenu
    assert "E2Q1" in contenu
    assert "Bonne réponse E1Q1" in contenu
    assert 'type="radio"' in contenu
    assert f'name="q_{questions["E1Q1"].pk}"' in contenu


def test_enregistrement_cree_participant_et_reponses_papier(
    client, proprietaire, groupe
):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {
            "action": "enregistrer",
            "eleve": marie.pk,
            f"q_{questions['E1Q1'].pk}": "A",
            f"q_{questions['E2Q1'].pk}": "B",
        },
    )

    assert reponse.status_code == 302
    assert reponse["Location"].endswith(f"?eleve={marie.pk}")
    participant = Participant.objects.get(session=session, student=marie)
    assert participant.couleur_assignee in (1, 2, 3, 4)
    reponses = Answer.objects.filter(participant=participant)
    assert reponses.count() == 2
    assert set(reponses.values_list("source", flat=True)) == {
        Answer.SOURCE_PAPIER
    }
    assert reponses.get(question=questions["E1Q1"]).choix_selectionnes == ["A"]


def test_enregistrement_ne_modifie_pas_une_reponse_app(
    client, proprietaire, groupe
):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    participant = Participant.objects.create(session=session, student=marie)
    Answer.objects.create(
        session=session,
        participant=participant,
        question=questions["E1Q1"],
        choix_selectionnes=["A"],
        source=Answer.SOURCE_APP,
        id_client=uuid.uuid4(),
    )
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {
            "action": "enregistrer",
            "eleve": marie.pk,
            f"q_{questions['E1Q1'].pk}": "B",
            f"q_{questions['E2Q1'].pk}": "A",
        },
        follow=True,
    )

    assert reponse.status_code == 200
    app = Answer.objects.get(participant=participant, question=questions["E1Q1"])
    assert app.source == Answer.SOURCE_APP
    assert app.choix_selectionnes == ["A"]
    papier = Answer.objects.get(
        participant=participant, question=questions["E2Q1"]
    )
    assert papier.source == Answer.SOURCE_PAPIER
    assert "1 réponse(s) de l'application conservée(s)" in _texte(reponse)


def test_enregistrement_met_a_jour_une_reponse_papier(
    client, proprietaire, groupe
):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    participant = Participant.objects.create(session=session, student=marie)
    Answer.objects.create(
        session=session,
        participant=participant,
        question=questions["E1Q1"],
        choix_selectionnes=["A"],
        source=Answer.SOURCE_PAPIER,
        id_client=uuid.uuid4(),
    )
    client.force_login(proprietaire)

    client.post(
        _url(session),
        {
            "action": "enregistrer",
            "eleve": marie.pk,
            f"q_{questions['E1Q1'].pk}": "B",
        },
    )

    reponse = Answer.objects.get(
        participant=participant, question=questions["E1Q1"]
    )
    assert reponse.choix_selectionnes == ["B"]
    assert reponse.source == Answer.SOURCE_PAPIER


def test_liaison_rapide_par_code_etudiant(client, proprietaire, groupe):
    session, _, paul, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {"action": "lier", "identifiant": "paul-mar00"},
    )

    assert reponse.status_code == 302
    assert reponse["Location"].endswith(f"?eleve={paul.pk}")
    assert Participant.objects.filter(session=session, student=paul).exists()


def test_liaison_rapide_par_identifiant_insa(client, proprietaire, groupe):
    session, _, paul, _ = _preparer(proprietaire, groupe)
    paul.identifiant_insa = "INS-PAUL"
    paul.save(update_fields=["identifiant_insa"])
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {"action": "lier", "identifiant": "ins-paul"},
    )

    assert reponse.status_code == 302
    assert Participant.objects.filter(session=session, student=paul).exists()


def test_liaison_rapide_identifiant_inconnu(client, proprietaire, groupe):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {"action": "lier", "identifiant": "INCONNU"},
    )

    assert reponse.status_code == 200
    assert "Aucun élève avec l'identifiant" in _texte(reponse)
    assert Participant.objects.filter(session=session).count() == 0


def test_liaison_rapide_eleve_hors_groupe(client, proprietaire, groupe):
    session, _, _, _ = _preparer(proprietaire, groupe)
    autre_groupe = Groupe.objects.create(
        nom="AUTRE", proprietaire=proprietaire
    )
    externe = creer_eleve(
        autre_groupe,
        nom="Externe",
        prenom="Alice",
        code_etudiant="ALICE-EXT00",
    )
    client.force_login(proprietaire)

    reponse = client.post(
        _url(session),
        {"action": "lier", "identifiant": externe.code_etudiant},
        follow=True,
    )

    assert Participant.objects.filter(session=session, student=externe).exists()
    assert "n'appartient pas au groupe" in _texte(reponse)


def test_import_csv_cree_reponses_et_participants(
    client, proprietaire, groupe
):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,E1Q1,A\n"
        "PAUL-MAR00,E2Q1,B\n"
    )

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
        follow=True,
    )

    assert reponse.status_code == 200
    assert Participant.objects.filter(session=session).count() == 2
    assert Answer.objects.filter(session=session).count() == 2
    assert set(
        Answer.objects.values_list("source", flat=True)
    ) == {Answer.SOURCE_PAPIER}
    assert "2 réponse(s) papier créée(s)" in _texte(reponse)


def test_import_csv_ignore_une_reponse_app(client, proprietaire, groupe):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    participant = Participant.objects.create(session=session, student=marie)
    Answer.objects.create(
        session=session,
        participant=participant,
        question=questions["E1Q1"],
        choix_selectionnes=["A"],
        source=Answer.SOURCE_APP,
        id_client=uuid.uuid4(),
    )
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,E1Q1,B\n"
        "MARIE-DUP00,E2Q1,A\n"
    )

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
        follow=True,
    )

    app = Answer.objects.get(
        participant=participant, question=questions["E1Q1"]
    )
    assert app.choix_selectionnes == ["A"]
    assert Answer.objects.filter(
        participant=participant, question=questions["E2Q1"]
    ).exists()
    assert "1 ignorée(s) car réponse application" in _texte(reponse)


def test_import_csv_met_a_jour_une_reponse_papier(
    client, proprietaire, groupe
):
    session, marie, _, questions = _preparer(proprietaire, groupe)
    participant = Participant.objects.create(session=session, student=marie)
    Answer.objects.create(
        session=session,
        participant=participant,
        question=questions["E1Q1"],
        choix_selectionnes=["A"],
        source=Answer.SOURCE_PAPIER,
        id_client=uuid.uuid4(),
    )
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,E1Q1,B\n"
    )

    client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
    )

    reponse = Answer.objects.get(
        participant=participant, question=questions["E1Q1"]
    )
    assert reponse.choix_selectionnes == ["B"]
    assert reponse.source == Answer.SOURCE_PAPIER


def test_import_csv_transactionnel_si_ligne_invalide(
    client, proprietaire, groupe
):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,E1Q1,A\n"
        "INCONNU,E2Q1,B\n"
    )

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
    )

    assert reponse.status_code == 200
    assert "aucun élève" in reponse.content.decode()
    assert Answer.objects.count() == 0
    assert Participant.objects.count() == 0


def test_import_csv_refuse_plusieurs_lettres_pour_unique(
    client, proprietaire, groupe
):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,E1Q1,AB\n"
    )

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
    )

    assert reponse.status_code == 200
    assert "qu'une seule lettre" in _texte(reponse)
    assert Answer.objects.count() == 0


def test_import_csv_refuse_uid_hors_du_quiz(client, proprietaire, groupe):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)
    contenu = (
        "identifiant,uid_question,lettre_choisie\n"
        "MARIE-DUP00,INCONNUE,A\n"
    )

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
    )

    assert reponse.status_code == 200
    assert "n'est pas dans le QCM" in _texte(reponse)
    assert Answer.objects.count() == 0


def test_import_csv_entete_invalide(client, proprietaire, groupe):
    session, _, _, _ = _preparer(proprietaire, groupe)
    client.force_login(proprietaire)
    contenu = "nom,question,lettre\nMARIE-DUP00,E1Q1,A\n"

    reponse = client.post(
        _url(session),
        {"action": "importer", "fichier": _fichier_csv(contenu)},
    )

    assert reponse.status_code == 200
    assert "En-tête CSV attendu" in _texte(reponse)
    assert Answer.objects.count() == 0


def test_import_csv_plusieurs_lettres_pour_question_multiple(
    client, proprietaire, groupe
):
    quiz = importer_quiz(
        {
            "titre": "Papier multiple",
            "questions": [
                {
                    "uid": "M1",
                    "etape": 1,
                    "duree_s": 60,
                    "enonce": "Question multiple",
                    "type": "multiple",
                    "choix": [
                        {"lettre": "A", "texte": "bonne 1", "correct": True},
                        {"lettre": "B", "texte": "bonne 2", "correct": True},
                        {"lettre": "C", "texte": "mauvaise", "correct": False},
                    ],
                }
            ],
        },
        proprietaire,
    )
    session = Session.objects.create(quiz=quiz, groupe=groupe)
    marie = creer_eleve(
        groupe, nom="Dupont", prenom="Marie", code_etudiant="MARIE-DUP00"
    )
    question = quiz.questions.get(uid="M1")
    client.force_login(proprietaire)

    page = _texte(client.get(f"{_url(session)}?eleve={marie.pk}"))
    assert 'type="checkbox"' in page

    client.post(
        _url(session),
        {
            "action": "enregistrer",
            "eleve": marie.pk,
            f"q_{question.pk}": ["A", "B"],
        },
    )

    participant = Participant.objects.get(session=session, student=marie)
    reponse = Answer.objects.get(participant=participant, question=question)
    assert reponse.choix_selectionnes == ["A", "B"]

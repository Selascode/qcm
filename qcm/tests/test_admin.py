"""Parcours professeur dans l'admin : créer une séance, ouvrir le tableau."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from qcm.import_questions import importer_quiz
from qcm.models import (
    Groupe,
    Participant,
    Question,
    QuestionSet,
    Quiz,
    QuizQuestion,
    Session,
    Student,
)
from qcm.tests.helpers import donnees_quiz

pytestmark = pytest.mark.django_db


def test_admin_cree_une_session_avec_code_et_lien_tableau(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(1, 1), administrateur)
    client.force_login(administrateur)

    formulaire = client.get("/admin/qcm/session/add/")
    assert formulaire.status_code == 200

    enregistrement = client.post(
        "/admin/qcm/session/add/",
        {"quiz": quiz.pk, "_save": "Enregistrer"},
    )
    assert enregistrement.status_code == 302

    session = Session.objects.get(quiz=quiz)
    assert len(session.code_session) == 6
    assert session.statut == Session.STATUT_ATTENTE

    page = client.get(f"/admin/qcm/session/{session.pk}/change/")
    assert page.status_code == 200

    liste = client.get("/admin/qcm/session/")
    assert liste.status_code == 200
    assert f"/tableau/{session.code_session}/" in liste.content.decode()


def test_admin_participants_affiche_la_colonne_groupe(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-groupe",
        email="admin-groupe@example.com",
        password="secret",
    )
    quiz = importer_quiz(donnees_quiz(1, 1), administrateur)
    session = Session.objects.create(quiz=quiz)
    Participant.objects.create(session=session)
    client.force_login(administrateur)

    liste = client.get("/admin/qcm/participant/")

    assert liste.status_code == 200
    contenu = liste.content.decode()
    assert "Groupe" in contenu
    assert "—" in contenu


def test_admin_inline_groupe_ajoute_un_eleve(client):
    administrateur = get_user_model().objects.create_superuser(
        username="admin-inline",
        email="admin-inline@example.com",
        password="secret",
    )
    groupe = Groupe.objects.create(nom="ISIA4", proprietaire=administrateur)
    client.force_login(administrateur)

    url = reverse("admin:qcm_groupe_change", args=[groupe.pk])
    reponse = client.post(
        url,
        {
            "nom": "ISIA4",
            "proprietaire": str(administrateur.pk),
            "etudiants-TOTAL_FORMS": "1",
            "etudiants-INITIAL_FORMS": "0",
            "etudiants-MIN_NUM_FORMS": "0",
            "etudiants-MAX_NUM_FORMS": "1000",
            "etudiants-0-nom": "Dupont",
            "etudiants-0-prenom": "Marie",
            "etudiants-0-code_etudiant": "",
            "_save": "Enregistrer",
        },
    )

    assert reponse.status_code == 302
    eleve = Student.objects.get(groupe=groupe)
    assert eleve.nom == "Dupont"
    assert eleve.prenom == "Marie"
    assert eleve.code_etudiant == "MARIE-DUP00"

    page = client.get(url)
    contenu = page.content.decode()
    assert "Dupont" in contenu
    assert "MARIE-DUP00" in contenu


def _quiz_avec_questions(proprietaire, *uids):
    # Les pages admin exigent un compte staff : le propriétaire du quiz joue
    # ici le rôle du professeur administrateur.
    if not proprietaire.is_superuser:
        proprietaire.is_staff = True
        proprietaire.is_superuser = True
        proprietaire.save()
    quiz = Quiz.objects.create(titre="Sélection", proprietaire=proprietaire)
    question_set = QuestionSet.objects.create(
        nom="Ensemble admin", proprietaire=proprietaire
    )
    questions = [
        Question.objects.create(
            set=question_set,
            uid=uid,
            enonce=f"Énoncé {uid}",
            type=Question.TYPE_UNIQUE,
        )
        for uid in uids
    ]
    return quiz, question_set, questions


def test_selection_ajoute_dans_l_ordre_et_ignore_les_doublons(
    client, proprietaire
):
    quiz, _, (q1, q2, q3) = _quiz_avec_questions(proprietaire, "Q1", "Q2", "Q3")
    client.force_login(proprietaire)
    url = reverse("admin:qcm_quiz_selection", args=[quiz.pk])

    reponse = client.post(
        url,
        {"action": "ajouter", "questions": [q2.pk, q1.pk]},
    )

    assert reponse.status_code == 302
    assert list(
        quiz.quiz_questions.order_by("position").values_list(
            "question_id", "position"
        )
    ) == [(q2.pk, 1), (q1.pk, 2)]

    client.post(url, {"action": "ajouter", "questions": [q1.pk]})
    client.post(url, {"action": "ajouter", "questions": [q3.pk]})

    assert list(
        quiz.quiz_questions.order_by("position").values_list(
            "question_id", "position"
        )
    ) == [(q2.pk, 1), (q1.pk, 2), (q3.pk, 3)]


def test_selection_retire_et_renumerote(client, proprietaire):
    quiz, _, (q1, q2, q3) = _quiz_avec_questions(proprietaire, "Q1", "Q2", "Q3")
    for position, question in enumerate((q1, q2, q3), start=1):
        QuizQuestion.objects.create(
            quiz=quiz, question=question, position=position
        )
    client.force_login(proprietaire)
    url = reverse("admin:qcm_quiz_selection", args=[quiz.pk])

    reponse = client.post(url, {"action": "retirer", "question": q2.pk})

    assert reponse.status_code == 302
    assert list(
        quiz.quiz_questions.order_by("position").values_list(
            "question_id", "position"
        )
    ) == [(q1.pk, 1), (q3.pk, 2)]


def test_selection_limitee_aux_ensembles_du_proprietaire(
    client, proprietaire, autre_proprietaire
):
    quiz, _, _ = _quiz_avec_questions(proprietaire, "Q1")
    autre_set = QuestionSet.objects.create(
        nom="Ensemble d'un autre", proprietaire=autre_proprietaire
    )
    autre_question = Question.objects.create(
        set=autre_set,
        uid="AUTRE",
        enonce="Pas à moi",
        type=Question.TYPE_UNIQUE,
    )
    client.force_login(proprietaire)
    url = reverse("admin:qcm_quiz_selection", args=[quiz.pk])

    page = client.get(url).content.decode()
    assert "Ensemble d'un autre" not in page

    client.post(
        url, {"action": "ajouter", "questions": [autre_question.pk]}
    )

    assert quiz.quiz_questions.count() == 0


def test_selection_refusee_pour_le_quiz_d_un_autre_prof(
    client, proprietaire, autre_proprietaire
):
    from django.contrib.auth.models import Permission

    quiz, _, _ = _quiz_avec_questions(proprietaire, "Q1")
    autre_proprietaire.is_staff = True
    autre_proprietaire.user_permissions.add(
        Permission.objects.get(codename="change_quiz")
    )
    autre_proprietaire.save()
    client.force_login(autre_proprietaire)

    reponse = client.get(
        reverse("admin:qcm_quiz_selection", args=[quiz.pk])
    )

    assert reponse.status_code == 403


def test_page_quiz_affiche_le_bouton_et_la_selection(client, proprietaire):
    quiz, _, (q1,) = _quiz_avec_questions(proprietaire, "Q1")
    QuizQuestion.objects.create(quiz=quiz, question=q1, position=1)
    client.force_login(proprietaire)

    page = client.get(f"/admin/qcm/quiz/{quiz.pk}/change/").content.decode()

    assert "Sélectionner les questions" in page
    assert "Q1" in page
    assert "Énoncé Q1" in page


def test_retrait_depuis_la_page_du_quiz(client, proprietaire):
    quiz, _, (q1,) = _quiz_avec_questions(proprietaire, "Q1")
    ligne = QuizQuestion.objects.create(quiz=quiz, question=q1, position=1)
    client.force_login(proprietaire)

    reponse = client.post(
        f"/admin/qcm/quiz/{quiz.pk}/change/",
        {
            "titre": quiz.titre,
            "proprietaire": str(proprietaire.pk),
            "penalite_active": "on",
            "facteur_penalite": "1.0",
            "duree_s": "60",
            "quiz_questions-TOTAL_FORMS": "1",
            "quiz_questions-INITIAL_FORMS": "1",
            "quiz_questions-MIN_NUM_FORMS": "0",
            "quiz_questions-MAX_NUM_FORMS": "1000",
            "quiz_questions-0-id": str(ligne.pk),
            "quiz_questions-0-quiz": str(quiz.pk),
            "quiz_questions-0-DELETE": "on",
            "_save": "Enregistrer",
        },
    )

    assert reponse.status_code == 302
    assert quiz.quiz_questions.count() == 0


def test_admin_ensemble_affiche_le_lien_d_import(client, proprietaire):
    _, question_set, _ = _quiz_avec_questions(proprietaire, "Q1")
    client.force_login(proprietaire)

    page = client.get(
        f"/admin/qcm/questionset/{question_set.pk}/change/"
    ).content.decode()

    assert "Q1" in page
    assert reverse(
        "qcm:importer_questions", args=[question_set.pk]
    ) in page

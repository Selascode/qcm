"""Helpers partagés par les tests."""

import json
import uuid
from datetime import timedelta

from django.utils import timezone

from qcm.models import Groupe, Session, Student
from qcm.services import demarrer_session


def donnees_quiz(
    nb_etapes: int = 5,
    questions_par_etape: int = 1,
    duree_s: int = 60,
    titre: str = "Quiz test",
) -> dict:
    questions = []
    for etape in range(1, nb_etapes + 1):
        for index in range(1, questions_par_etape + 1):
            uid = f"E{etape}Q{index}"
            questions.append(
                {
                    "uid": uid,
                    "etape": etape,
                    "duree_s": duree_s,
                    "enonce": f"Énoncé très secret {uid}",
                    "type": "unique",
                    "choix": [
                        {
                            "lettre": "A",
                            "texte": f"Bonne réponse {uid}",
                            "correct": True,
                        },
                        {
                            "lettre": "B",
                            "texte": f"Mauvaise réponse {uid}",
                            "correct": False,
                        },
                        {
                            "lettre": "C",
                            "texte": f"Autre réponse {uid}",
                            "correct": False,
                        },
                    ],
                }
            )
    return {"titre": titre, "questions": questions}


def creer_session(quiz) -> Session:
    return Session.objects.create(quiz=quiz)


def demarrer(session: Session) -> Session:
    return demarrer_session(session)


def en_tetes(jeton) -> dict:
    return {"X-Jeton": str(jeton)}


def rejoindre(client, session: Session) -> dict:
    reponse = client.post(
        "/api/rejoindre/",
        data=json.dumps({"code": session.code_session}),
        content_type="application/json",
    )
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["ok"] is True
    return donnees


def etat(client, jeton):
    return client.get("/api/etat/", headers=en_tetes(jeton))


def repondre(client, jeton, question_uid: str, choix, id_client=None):
    id_client = str(id_client or uuid.uuid4())
    return client.post(
        "/api/repondre/",
        data=json.dumps(
            {
                "id_client": id_client,
                "question_uid": question_uid,
                "choix": choix,
            }
        ),
        content_type="application/json",
        headers=en_tetes(jeton),
    )


def piloter(client, session: Session, action: str, delta=None):
    corps = {"code": session.code_session, "action": action}
    if delta is not None:
        corps["delta"] = delta
    return client.post(
        "/api/piloter/",
        data=json.dumps(corps),
        content_type="application/json",
    )


def expirer_etape(session: Session) -> None:
    """Place ``ends_at`` dans le passé pour déclencher l'auto-avance."""
    Session.objects.filter(pk=session.pk).update(
        ends_at=timezone.now() - timedelta(seconds=1)
    )
    session.refresh_from_db()


def creer_groupe(proprietaire, nom: str = "ISIA4") -> Groupe:
    return Groupe.objects.create(nom=nom, proprietaire=proprietaire)


def creer_eleve(
    groupe: Groupe,
    *,
    nom: str = "Dupont",
    prenom: str = "Marie",
    code_etudiant: str = "MD0001",
    identifiant_insa: str | None = None,
) -> Student:
    return Student.objects.create(
        nom=nom,
        prenom=prenom,
        code_etudiant=code_etudiant,
        identifiant_insa=identifiant_insa,
        groupe=groupe,
    )


def rejoindre_eleve(
    client,
    session: Session,
    code_etudiant: str,
    jeton: str | None = None,
):
    corps = {
        "code": session.code_session,
        "code_etudiant": code_etudiant,
    }
    if jeton is not None:
        corps["jeton"] = jeton
    return client.post(
        "/api/rejoindre/",
        data=json.dumps(corps),
        content_type="application/json",
    )


def etat_participants(client, session: Session):
    return client.get(
        "/api/etat_participants/",
        {"code": session.code_session},
    )

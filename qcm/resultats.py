"""Résultats d'une séance, calculés à la volée (rien n'est stocké).

Le taux de réussite d'une question est la part des réponses reçues qui sont
entièrement correctes (note ``1.0``). Les réponses partielles ne comptent pas
comme une réussite, mais restent visibles dans la note de l'élève.
"""

from collections import defaultdict

from qcm.models import Answer
from qcm.notation import note_question, note_seance


def _questions_du_quiz(quiz) -> list:
    return [
        ligne.question
        for ligne in quiz.quiz_questions.select_related("question")
        .prefetch_related("question__choices")
        .order_by("position", "id")
    ]


def calculer_resultats(session) -> dict:
    """Retourne les notes par participant et les statistiques par question."""
    quiz = session.quiz
    questions = _questions_du_quiz(quiz)
    participants = list(
        session.participants.select_related("student").order_by("id")
    )

    reponses: dict[int, dict[int, Answer]] = defaultdict(dict)
    for answer in Answer.objects.filter(session=session).only(
        "participant_id",
        "question_id",
        "choix_selectionnes",
    ):
        reponses[answer.question_id][answer.participant_id] = answer

    lignes_participants = []
    for participant in participants:
        notes = []
        detail = []
        for question in questions:
            answer = reponses[question.pk].get(participant.pk)
            note = note_question(
                answer.choix_selectionnes if answer else [],
                question,
                penalite_active=quiz.penalite_active,
                facteur_penalite=quiz.facteur_penalite,
            )
            notes.append(note)
            detail.append(
                {
                    "question": question,
                    "note": note,
                    "repondu": answer is not None,
                    "choix": answer.choix_selectionnes if answer else [],
                }
            )
        lignes_participants.append(
            {
                "participant": participant,
                "notes": detail,
                "total": note_seance(notes),
            }
        )

    lignes_participants.sort(
        key=lambda ligne: (-ligne["total"], ligne["participant"].pk)
    )

    stats_questions = []
    for question in questions:
        par_participant = reponses[question.pk]
        nb_reponses = len(par_participant)
        nb_correctes = 0
        for answer in par_participant.values():
            note = note_question(
                answer.choix_selectionnes,
                question,
                penalite_active=quiz.penalite_active,
                facteur_penalite=quiz.facteur_penalite,
            )
            if abs(note - 1.0) < 1e-9:
                nb_correctes += 1
        stats_questions.append(
            {
                "question": question,
                "nb_reponses": nb_reponses,
                "nb_correctes": nb_correctes,
                "taux_reussite": (
                    nb_correctes / nb_reponses * 100 if nb_reponses else None
                ),
            }
        )

    return {
        "lignes_participants": lignes_participants,
        "stats_questions": stats_questions,
        "nb_participants": len(participants),
    }

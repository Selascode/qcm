"""Barème du QCM : fonctions pures, sans accès à la base (AGENTS.md §4).

Le barème n'est jamais stocké ni dupliqué dans une vue : chaque fonction reçoit
explicitement sa configuration (pénalité, facteur) et la question avec ses choix.
"""

from qcm.models import Question


def note_question(
    choix_selectionnes: list[str],
    question: Question,
    *,
    penalite_active: bool = True,
    facteur_penalite: float = 1.0,
) -> float:
    """Note d'une question, bornée entre ``-facteur_penalite`` et ``1``.

    - ``choix_selectionnes`` : lettres cochées (ex. ``["A", "C"]``) ;
    - ``question`` : instance dont les ``Choice`` portent ``est_correct`` ;
    - ``penalite_active`` : si ``False``, une mauvaise réponse contribue à 0 ;
    - ``facteur_penalite`` : multiplicateur des mauvaises réponses (> 0).

    Formule : ``(bonnes_cochées - facteur * mauvaises_cochées) / nb_bonnes``.
    Une absence de réponse vaut ``0`` et une question sans bonne réponse
    (donnée invalide) vaut aussi ``0`` plutôt que de diviser par zéro.
    """
    if facteur_penalite is None or facteur_penalite <= 0:
        raise ValueError("Le facteur de pénalité doit être strictement positif.")

    choix = list(question.choices.all())
    bonnes = {c.lettre for c in choix if c.est_correct}
    if not bonnes:
        return 0.0

    selection = set(choix_selectionnes or [])
    bonnes_cochees = len(selection & bonnes)
    if penalite_active:
        mauvaises = {c.lettre for c in choix if not c.est_correct}
        mauvaises_cochees = len(selection & mauvaises)
    else:
        mauvaises_cochees = 0

    brut = (bonnes_cochees - facteur_penalite * mauvaises_cochees) / len(bonnes)
    return max(-facteur_penalite, min(1.0, brut))


def note_seance(notes_questions: list[float]) -> float:
    """Note finale d'une séance : ``max(0, somme des notes de questions)``.

    La somme n'est pas plafonnée ; seul le total final est ramené à 0 minimum.
    """
    return max(0.0, sum(notes_questions))

"""Règles de séance : horloge serveur, pilotage et cible de réponse.

Toute décision temporelle est prise ici, à partir de ``Session.ends_at``.
Aucune vue ne calcule un temps restant à partir de l'horloge du client.
"""

import io
import random
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from qcm.models import Answer, Session


class ErreurPilotage(ValueError):
    """Action de pilotage refusée (état de séance incompatible)."""


def _maintenant(maintenant):
    return maintenant or timezone.now()


def temps_restant_s(session: Session, maintenant=None) -> int | None:
    """Temps restant côté serveur, en secondes entières, ou ``None``."""
    if session.statut == Session.STATUT_PAUSE:
        return session.reste_en_pause
    if session.statut != Session.STATUT_EN_COURS or session.ends_at is None:
        return None
    return max(0, int((session.ends_at - _maintenant(maintenant)).total_seconds()))


def _session_verrouillee(session_id: int) -> Session:
    return Session.objects.select_for_update().select_related("quiz").get(pk=session_id)


def _etapes_ordonnees(session: Session) -> list:
    etapes = list(session.quiz.steps.order_by("numero"))
    numeros = [etape.numero for etape in etapes]
    if numeros != list(range(1, len(etapes) + 1)):
        raise ErreurPilotage("Les étapes doivent être numérotées 1, 2, 3… sans trou.")
    return etapes


def _avancer(session: Session, maintenant) -> Session:
    """Avance d'une étape (ou termine). Une seule étape à la fois."""
    etapes = _etapes_ordonnees(session)
    if session.etape_courante < 1:
        session.etape_courante = 1
        if etapes:
            session.ends_at = maintenant + timedelta(seconds=etapes[0].duree_s)
            session.statut = Session.STATUT_EN_COURS
            session.reste_en_pause = None
        else:
            session.statut = Session.STATUT_FINI
            session.ends_at = None
    elif session.etape_courante < len(etapes):
        session.etape_courante += 1
        session.ends_at = maintenant + timedelta(
            seconds=etapes[session.etape_courante - 1].duree_s
        )
        session.statut = Session.STATUT_EN_COURS
        session.reste_en_pause = None
    else:
        session.statut = Session.STATUT_FINI
        session.ends_at = None
        session.reste_en_pause = None
    session.save(
        update_fields=[
            "etape_courante",
            "ends_at",
            "statut",
            "reste_en_pause",
        ]
    )
    return session


def avancer_si_necessaire(session: Session, maintenant=None) -> Session:
    """Avance la séance si ``now() > ends_at``. Idempotent et verrouillé."""
    maintenant = _maintenant(maintenant)
    if session.statut != Session.STATUT_EN_COURS or session.ends_at is None:
        return session
    if maintenant <= session.ends_at:
        return session
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_EN_COURS or session.ends_at is None:
            return session
        if maintenant <= session.ends_at:
            return session
        return _avancer(session, maintenant)


def demarrer_session(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_ATTENTE:
            raise ErreurPilotage("La séance n'est pas en attente.")
        etapes = _etapes_ordonnees(session)
        if not etapes:
            raise ErreurPilotage("Le QCM ne contient aucune étape.")
        session.statut = Session.STATUT_EN_COURS
        session.etape_courante = 1
        session.ends_at = maintenant + timedelta(seconds=etapes[0].duree_s)
        session.reste_en_pause = None
        session.save(
            update_fields=[
                "statut",
                "etape_courante",
                "ends_at",
                "reste_en_pause",
            ]
        )
        return session


def mettre_en_pause(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_EN_COURS:
            raise ErreurPilotage("La séance n'est pas en cours.")
        if session.ends_at is None:
            raise ErreurPilotage("La séance n'a pas de minuteur actif.")
        reste = max(0, int((session.ends_at - maintenant).total_seconds()))
        session.statut = Session.STATUT_PAUSE
        session.reste_en_pause = reste
        session.ends_at = None
        session.save(update_fields=["statut", "reste_en_pause", "ends_at"])
        return session


def reprendre(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_PAUSE:
            raise ErreurPilotage("La séance n'est pas en pause.")
        reste = session.reste_en_pause or 0
        session.statut = Session.STATUT_EN_COURS
        session.ends_at = maintenant + timedelta(seconds=reste)
        session.reste_en_pause = None
        session.save(update_fields=["statut", "ends_at", "reste_en_pause"])
        return session


def ajouter_temps(session: Session, secondes, maintenant=None) -> Session:
    if (
        not isinstance(secondes, int)
        or isinstance(secondes, bool)
        or not 1 <= secondes <= 3600
    ):
        raise ErreurPilotage(
            "Le temps à ajouter doit être un entier entre 1 et 3600 secondes."
        )
    _ = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut == Session.STATUT_EN_COURS:
            if session.ends_at is None:
                raise ErreurPilotage("La séance n'a pas de minuteur actif.")
            session.ends_at = session.ends_at + timedelta(seconds=secondes)
            session.save(update_fields=["ends_at"])
        elif session.statut == Session.STATUT_PAUSE:
            session.reste_en_pause = (session.reste_en_pause or 0) + secondes
            session.save(update_fields=["reste_en_pause"])
        else:
            raise ErreurPilotage("La séance n'est ni en cours ni en pause.")
        return session


def etape_suivante(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut not in (
            Session.STATUT_EN_COURS,
            Session.STATUT_PAUSE,
        ):
            raise ErreurPilotage("La séance n'est pas active.")
        if session.statut == Session.STATUT_PAUSE:
            session.statut = Session.STATUT_EN_COURS
            session.reste_en_pause = None
        return _avancer(session, maintenant)


def etape_precedente(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut not in (
            Session.STATUT_EN_COURS,
            Session.STATUT_PAUSE,
        ):
            raise ErreurPilotage("La séance n'est pas active.")
        etapes = _etapes_ordonnees(session)
        if session.etape_courante <= 1:
            raise ErreurPilotage("La séance est déjà à la première étape.")
        if session.etape_courante > len(etapes):
            raise ErreurPilotage("Étape courante incohérente.")
        session.etape_courante -= 1
        session.statut = Session.STATUT_EN_COURS
        session.ends_at = maintenant + timedelta(
            seconds=etapes[session.etape_courante - 1].duree_s
        )
        session.reste_en_pause = None
        session.save(
            update_fields=[
                "etape_courante",
                "statut",
                "ends_at",
                "reste_en_pause",
            ]
        )
        return session


def question_courante_pour(session: Session, participant):
    """Question que ce participant doit traiter à l'étape courante.

    La couleur de l'élève distribue les participants sur les questions
    présentes. Avec 4 questions, chaque couleur tombe sur sa colonne ; avec
    moins de questions, on replie modulo le nombre de questions pour que
    chaque élève ait toujours une question à traiter.
    """
    etape = session.quiz.steps.filter(numero=session.etape_courante).first()
    if etape is None:
        return None
    questions = list(etape.questions.order_by("ordre", "id"))
    if not questions:
        return None
    index = (participant.couleur_assignee - 1) % len(questions)
    return questions[index]


def lettres_melangees(participant, question) -> list[str]:
    """Ordre des boutons propre à l'élève, stable après redémarrage."""
    lettres = [choix.lettre for choix in question.choices.order_by("position", "id")]
    aleatoire = random.Random(f"{participant.graine_melange}:{question.pk}")
    aleatoire.shuffle(lettres)
    return lettres


def compter_reponses_par_question(session: Session, questions) -> dict[int, int]:
    identifiants = [question.pk for question in questions]
    if not identifiants:
        return {}
    lignes = (
        Answer.objects.filter(question_id__in=identifiants)
        .values("question_id")
        .annotate(nombre=Count("id"))
    )
    return {ligne["question_id"]: ligne["nombre"] for ligne in lignes}


def generer_qr_svg(url: str) -> str:
    """QR code SVG du lien de connexion (aucune donnée sensible)."""
    image = qrcode.make(
        url,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    tampon = io.BytesIO()
    image.save(tampon)
    return tampon.getvalue().decode("utf-8")

"""Règles de séance : horloge serveur, pilotage et cible de réponse.

Toute décision temporelle est prise ici, à partir de ``Session.ends_at``.
Aucune vue ne calcule un temps restant à partir de l'horloge du client.
"""

import io
import random
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from qcm.couleurs import infos_couleur
from qcm.models import Answer, Participant, Session


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


def terminer_session(session: Session) -> Session:
    """Clôture explicite de la séance (statut ``fini``). Idempotent."""
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut == Session.STATUT_FINI:
            return session
        session.statut = Session.STATUT_FINI
        session.ends_at = None
        session.reste_en_pause = None
        session.save(update_fields=["statut", "ends_at", "reste_en_pause"])
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


def construire_url_rejoindre(request, session: Session) -> str:
    """URL absolue à encoder dans le QR code d'une séance.

    ``QCM_LAN_HOST`` (format ``ip:port``) permet au téléphone de joindre le
    serveur sur le réseau local. Sans configuration, on garde l'URL de la
    requête, pour ne pas casser la démo locale sur l'ordinateur.
    """
    chemin = reverse("qcm:rejoindre", args=[session.code_session])
    hote = (settings.QCM_LAN_HOST or "").strip()
    if hote:
        return f"http://{hote.rstrip('/')}{chemin}"
    return request.build_absolute_uri(chemin)


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


def _secondes_depuis(maintenant, instant) -> int | None:
    if instant is None:
        return None
    return max(0, int((maintenant - instant).total_seconds()))


def marquer_activite(participant, maintenant=None) -> None:
    """Met à jour la dernière activité, au plus toutes les 10 secondes.

    Le polling est de 1 à 2 s : sans seuil, chaque élève écrirait en base à
    chaque requête. Dix secondes suffisent pour l'indicateur « il y a X s ».
    La colonne n'est jamais remise à ``NULL`` : le statut « Connecté » reste
    acquis pendant la séance.
    """
    maintenant = _maintenant(maintenant)
    seuil = maintenant - timedelta(seconds=10)
    (
        Participant.objects.filter(pk=participant.pk)
        .filter(Q(derniere_activite__isnull=True) | Q(derniere_activite__lt=seuil))
        .update(derniere_activite=maintenant)
    )


def etat_participants(session: Session, maintenant=None) -> dict:
    """Données du panneau participants, sans PIN, hash ni réponse.

    Séance rattachée à un groupe : la liste complète des élèves du groupe, avec
    ``connecte`` (irréversible) et ``derniere_activite_s``. Séance libre :
    uniquement les participants effectivement connectés.
    """
    maintenant = _maintenant(maintenant)

    if session.groupe_id is None:
        libres = []
        for participant in session.participants.select_related("student").order_by(
            "id"
        ):
            libres.append(
                {
                    "participant_id": participant.pk,
                    "nom": participant.student.nom
                    if participant.student_id
                    else None,
                    "prenom": participant.student.prenom
                    if participant.student_id
                    else None,
                    "code_etudiant": participant.student.code_etudiant
                    if participant.student_id
                    else None,
                    "symbole": participant.symbole,
                    "couleur": infos_couleur(participant.couleur_assignee),
                    "connecte": participant.derniere_activite is not None,
                    "derniere_activite_s": _secondes_depuis(
                        maintenant, participant.derniere_activite
                    ),
                }
            )
        return {
            "ok": True,
            "groupe": None,
            "connectes": len(libres),
            "total": len(libres),
            "participants": libres,
        }

    participants = {
        participant.student_id: participant
        for participant in session.participants.filter(student__isnull=False).only(
            "student_id",
            "derniere_activite",
            "couleur_assignee",
        )
    }
    lignes = []
    for student in session.groupe.etudiants.order_by("nom", "prenom"):
        participant = participants.get(student.pk)
        lignes.append(
            {
                "participant_id": participant.pk if participant else None,
                "nom": student.nom,
                "prenom": student.prenom,
                "code_etudiant": student.code_etudiant,
                "symbole": participant.symbole if participant else None,
                "couleur": infos_couleur(participant.couleur_assignee)
                if participant
                else None,
                "connecte": participant is not None
                and participant.derniere_activite is not None,
                "derniere_activite_s": _secondes_depuis(
                    maintenant, participant.derniere_activite
                )
                if participant
                else None,
            }
        )
    connectes = sum(1 for ligne in lignes if ligne["connecte"])
    return {
        "ok": True,
        "groupe": session.groupe.nom,
        "connectes": connectes,
        "total": len(lignes),
        "participants": lignes,
    }

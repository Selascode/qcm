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

from qcm.couleurs import NB_COULEURS, infos_couleur
from qcm.models import Answer, Participant, Session
from qcm.services.repartition import EtapeVirtuelle, generer_etapes

# Délai après ``ends_at`` pendant lequel la séance reste « en cours » avant
# l'auto-avance. Il laisse à la page de présentation le temps de mettre la
# séance en pause pour afficher les statistiques de fin d'étape (V4) ; les
# réponses reçues après ``ends_at`` restent refusées pendant cette marge.
MARGE_FIN_ETAPE_S = 2


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


def questions_du_quiz(quiz) -> list:
    """Questions sélectionnées, dans l'ordre du panier (``QuizQuestion``)."""
    return [
        ligne.question
        for ligne in quiz.quiz_questions.select_related("question")
        .prefetch_related("question__choices")
        .order_by("position", "id")
    ]


def etapes_virtuelles(session: Session) -> list[EtapeVirtuelle]:
    """Étapes affichées : T étapes virtuelles pour un paquet de T questions."""
    return generer_etapes(questions_du_quiz(session.quiz))


def nombre_etapes(session: Session) -> int:
    """Nombre d'étapes affichées (et non de paquets stockés)."""
    return len(etapes_virtuelles(session))


def _etape_virtuelle(session: Session, numero: int) -> EtapeVirtuelle | None:
    etapes = etapes_virtuelles(session)
    if 1 <= numero <= len(etapes):
        return etapes[numero - 1]
    return None


def questions_de_l_etape(session: Session, numero: int) -> list:
    """Questions du paquet affiché à l'étape virtuelle ``numero``."""
    etape = _etape_virtuelle(session, numero)
    if etape is None:
        return []
    return list(etape.paquet)


def position_question_dans_etape(
    session: Session, numero: int, question
) -> int | None:
    """Position 1..T de la question dans le paquet affiché (couleur)."""
    etape = _etape_virtuelle(session, numero)
    if etape is None:
        return None
    for position, candidate in enumerate(etape.paquet, start=1):
        if candidate.pk == question.pk:
            return position
    return None


def _duree_etape(session: Session, numero: int) -> int:
    etape = _etape_virtuelle(session, numero)
    if etape is None:
        raise ErreurPilotage("Étape courante incohérente.")
    durees = [question.duree_s for question in etape.paquet]
    return max([session.quiz.duree_s, *durees])


def _avancer(session: Session, maintenant) -> Session:
    """Avance d'une étape virtuelle (ou termine). Une seule étape à la fois."""
    total = nombre_etapes(session)
    if session.etape_courante < 1:
        session.etape_courante = 1
        if total:
            session.ends_at = maintenant + timedelta(
                seconds=_duree_etape(session, 1)
            )
            session.statut = Session.STATUT_EN_COURS
            session.reste_en_pause = None
        else:
            session.statut = Session.STATUT_FINI
            session.ends_at = None
    elif session.etape_courante < total:
        session.etape_courante += 1
        session.ends_at = maintenant + timedelta(
            seconds=_duree_etape(session, session.etape_courante)
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
    """Avance la séance après ``ends_at`` + marge de fin d'étape.

    La marge ``MARGE_FIN_ETAPE_S`` laisse le temps à la présentation de
    demander la pause et d'afficher les statistiques. Pendant cette marge, la
    séance reste ``en_cours`` avec ``temps_restant_s == 0`` : aucune réponse
    n'est acceptée (``repondre`` compare toujours à ``ends_at``).
    """
    maintenant = _maintenant(maintenant)
    if session.statut != Session.STATUT_EN_COURS or session.ends_at is None:
        return session
    if maintenant <= session.ends_at + timedelta(seconds=MARGE_FIN_ETAPE_S):
        return session
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_EN_COURS or session.ends_at is None:
            return session
        if maintenant <= session.ends_at + timedelta(seconds=MARGE_FIN_ETAPE_S):
            return session
        return _avancer(session, maintenant)


def demarrer_session(session: Session, maintenant=None) -> Session:
    maintenant = _maintenant(maintenant)
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut != Session.STATUT_ATTENTE:
            raise ErreurPilotage("La séance n'est pas en attente.")
        total = nombre_etapes(session)
        if not total:
            raise ErreurPilotage("Le QCM ne contient aucune question.")
        session.statut = Session.STATUT_EN_COURS
        session.etape_courante = 1
        session.ends_at = maintenant + timedelta(seconds=_duree_etape(session, 1))
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


def mettre_en_pause_fin_etape(
    session: Session, etape_attendue, maintenant=None
) -> Session:
    """Met en pause la fin de l'étape, pour figer les statistiques.

    Appelée par la page de présentation à l'expiration du minuteur. L'étape
    attendue évite de mettre en pause l'étape suivante si l'auto-avance a déjà
    eu lieu. L'action est idempotente si la séance est déjà en pause.

    Le temps restant est volontairement remis à zéro : cette pause marque la
    fin de l'étape, le professeur reprend avec « Suivant ».
    """
    if not isinstance(etape_attendue, int) or isinstance(etape_attendue, bool):
        raise ErreurPilotage("Étape attendue invalide.")
    with transaction.atomic():
        session = _session_verrouillee(session.pk)
        if session.statut == Session.STATUT_PAUSE:
            return session
        if session.statut != Session.STATUT_EN_COURS:
            raise ErreurPilotage("La séance n'est pas en cours.")
        if session.etape_courante != etape_attendue:
            raise ErreurPilotage("L'étape a déjà changé.")
        if session.ends_at is None:
            raise ErreurPilotage("La séance n'a pas de minuteur actif.")
        session.statut = Session.STATUT_PAUSE
        session.reste_en_pause = 0
        session.ends_at = None
        session.save(update_fields=["statut", "reste_en_pause", "ends_at"])
        return session


def fin_etape_atteinte(session: Session, maintenant=None) -> bool:
    """Vrai si l'étape courante est finie (pause ou minuteur écoulé)."""
    if session.statut == Session.STATUT_PAUSE:
        return True
    return (
        session.statut == Session.STATUT_EN_COURS
        and temps_restant_s(session, maintenant) == 0
    )


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
        if session.etape_courante <= 1:
            raise ErreurPilotage("La séance est déjà à la première étape.")
        if session.etape_courante > nombre_etapes(session):
            raise ErreurPilotage("Étape courante incohérente.")
        session.etape_courante -= 1
        session.statut = Session.STATUT_EN_COURS
        session.ends_at = maintenant + timedelta(
            seconds=_duree_etape(session, session.etape_courante)
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
    """Question que ce participant doit traiter à l'étape virtuelle courante.

    La couleur initiale tourne à chaque étape du paquet :
    ``(couleur_initiale - 1 + étape_dans_paquet) % T + 1``. En T étapes, chaque
    élève répond donc à toutes les questions du paquet.
    """
    etape = _etape_virtuelle(session, session.etape_courante)
    if etape is None or not etape.paquet:
        return None
    questions = list(etape.paquet)
    taille = len(questions)
    couleur = (
        (participant.couleur_assignee - 1 + etape.index_dans_paquet) % taille + 1
    )
    return questions[couleur - 1]


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
        Answer.objects.filter(session=session, question_id__in=identifiants)
        .values("question_id")
        .annotate(nombre=Count("id"))
    )
    return {ligne["question_id"]: ligne["nombre"] for ligne in lignes}


def statistiques_etape(session: Session, numero=None) -> list[dict]:
    """Répartition des réponses par choix pour les questions d'une étape.

    Le pourcentage porte sur les élèves ayant répondu à la question (une
    question sans réponse vaut 0 %). Une réponse à choix multiple compte dans
    chaque lettre cochée : la somme des pourcentages peut donc dépasser 100 %.
    La fonction ne lit que des réponses déjà enregistrées et ne renvoie jamais
    de note.
    """
    numero = session.etape_courante if numero is None else numero
    questions = questions_de_l_etape(session, numero)
    if not questions:
        return []

    reponses = Answer.objects.filter(
        session=session, question__in=questions
    ).values_list("question_id", "choix_selectionnes")
    selections_par_question: dict[int, list[list[str]]] = {
        question.pk: [] for question in questions
    }
    for question_id, choix in reponses:
        selections_par_question[question_id].append(list(choix or []))

    resultats = []
    for position, question in enumerate(questions, start=1):
        selections = selections_par_question[question.pk]
        total = len(selections)
        choix_statistiques = []
        for choix in question.choices.all():
            nombre = sum(
                1 for reponse in selections if choix.lettre in reponse
            )
            pourcentage = round(100 * nombre / total, 1) if total else 0.0
            choix_statistiques.append(
                {
                    "lettre": choix.lettre,
                    "texte": choix.texte,
                    "est_correct": choix.est_correct,
                    "nombre": nombre,
                    "pourcentage": pourcentage,
                    "largeur": f"{pourcentage:.1f}",
                    "pourcentage_affiche": f"{pourcentage:.0f}",
                }
            )
        resultats.append(
            {
                "question": question,
                "couleur": infos_couleur(position),
                "nb_reponses": total,
                "choix": choix_statistiques,
            }
        )
    return resultats


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


def prochaine_couleur(session: Session) -> int:
    """Couleur Round-Robin d'un nouvel élève : 1, 2, 3, 4, 1, 2…

    Le compteur porte sur les participants déjà présents dans la session ;
    un élève qui se reconnecte garde son ``Participant`` et sa couleur.
    """
    deja = Participant.objects.filter(session=session).count()
    return (deja % NB_COULEURS) + 1


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

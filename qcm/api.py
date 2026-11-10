"""Endpoints JSON élève et professeur.

Sécurité : les réponses destinées aux élèves ne contiennent jamais l'énoncé,
le texte des choix ni ``est_correct``. Seuls la couleur, le symbole, le nombre
de choix, les lettres, le temps restant et l'état de la réponse transitent.
"""

import json
import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from qcm import services
from qcm.couleurs import infos_couleur
from qcm.models import Answer, Participant, Question, Session, Student


def _json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _erreur(raison: str, status: int = 400, **extra) -> JsonResponse:
    return JsonResponse({"ok": False, "raison": raison, **extra}, status=status)


def _participant(request):
    valeur = request.headers.get("X-Jeton")
    if not valeur:
        return None
    try:
        jeton = uuid.UUID(valeur)
    except (TypeError, ValueError, AttributeError):
        return None
    participant = (
        Participant.objects.select_related("session__quiz")
        .filter(jeton_appareil=jeton)
        .first()
    )
    if participant is not None:
        services.marquer_activite(participant)
    return participant


def _couleur_question(question: Question) -> dict:
    return infos_couleur(question.couleur_slot)


def _reponse_participant(session: Session, participant: Participant) -> JsonResponse:
    return JsonResponse(
        {
            "ok": True,
            "code": session.code_session,
            "session_id": session.pk,
            "participant_id": participant.pk,
            "jeton": str(participant.jeton_appareil),
            "couleur": infos_couleur(participant.couleur_assignee),
            "statut": session.statut,
        }
    )


def _rejoindre_groupe(donnees, session: Session) -> JsonResponse:
    """Connexion d'un élève identifié : code de session + identifiant."""
    code_etudiant = str(donnees.get("code_etudiant") or "").strip()
    if not code_etudiant:
        return _erreur("identifiant_requis")

    student = Student.objects.filter(
        code_etudiant__iexact=code_etudiant,
        groupe_id=session.groupe_id,
    ).first()
    if student is None:
        return _erreur("identifiant_inconnu", 404)

    maintenant = timezone.now()
    with transaction.atomic():
        participant = (
            Participant.objects.select_for_update()
            .filter(session=session, student=student)
            .first()
        )
        if participant is None:
            try:
                with transaction.atomic():
                    participant = Participant.objects.create(
                        session=session,
                        student=student,
                        derniere_activite=maintenant,
                    )
            except IntegrityError:
                participant = Participant.objects.select_for_update().get(
                    session=session,
                    student=student,
                )
                participant.jeton_appareil = uuid.uuid4()
                participant.derniere_activite = maintenant
                participant.save(
                    update_fields=["jeton_appareil", "derniere_activite"]
                )
        else:
            # Un seul appareil actif : l'ancien jeton ne répond plus (401).
            participant.jeton_appareil = uuid.uuid4()
            participant.derniere_activite = maintenant
            participant.save(update_fields=["jeton_appareil", "derniere_activite"])

    return _reponse_participant(session, participant)


@csrf_exempt
@require_POST
def rejoindre(request):
    donnees = _json(request)
    if not isinstance(donnees, dict):
        return _erreur("json_invalide")
    code = str(donnees.get("code") or "").strip().upper()
    session = (
        Session.objects.select_related("quiz", "groupe")
        .filter(code_session=code)
        .first()
    )
    if session is None:
        return _erreur("code_inconnu", 404)

    if session.groupe_id is not None:
        return _rejoindre_groupe(donnees, session)

    participant = None
    jeton_brut = donnees.get("jeton")
    if jeton_brut:
        try:
            jeton = uuid.UUID(str(jeton_brut))
        except (TypeError, ValueError, AttributeError):
            jeton = None
        if jeton is not None:
            participant = Participant.objects.filter(
                session=session, jeton_appareil=jeton
            ).first()
    if participant is None:
        participant = Participant.objects.create(
            session=session,
            derniere_activite=timezone.now(),
        )
    else:
        services.marquer_activite(participant)

    return _reponse_participant(session, participant)


def _etat_question(participant, question) -> dict:
    couleur = _couleur_question(question)
    return {
        "couleur": couleur,
        "symbole": couleur["symbole"],
        "nb_choix": question.choices.count(),
        "lettres": services.lettres_melangees(participant, question),
        "question_uid": question.uid,
        "deja_repondu": Answer.objects.filter(
            participant=participant, question=question
        ).exists(),
    }


def _etat_sans_question() -> dict:
    return {
        "couleur": None,
        "symbole": None,
        "nb_choix": 0,
        "lettres": [],
        "question_uid": None,
        "deja_repondu": False,
    }


@csrf_exempt
@require_GET
def etat_eleve(request):
    participant = _participant(request)
    if participant is None:
        return _erreur("jeton_invalide", 401)

    session = services.avancer_si_necessaire(participant.session)
    base = {
        "ok": True,
        "statut": session.statut,
        "etape": session.etape_courante,
        "nb_etapes": services.nombre_etapes(session),
    }

    if session.statut in (
        Session.STATUT_EN_COURS,
        Session.STATUT_PAUSE,
    ):
        question = services.question_courante_pour(session, participant)
        etat = {
            **base,
            "temps_restant_s": services.temps_restant_s(session),
        }
        if question is None:
            etat.update(_etat_sans_question())
        else:
            etat.update(_etat_question(participant, question))
        return JsonResponse(etat)

    return JsonResponse(
        {
            **base,
            "temps_restant_s": None,
            **_etat_sans_question(),
        }
    )


@csrf_exempt
@require_POST
def repondre(request):
    participant = _participant(request)
    if participant is None:
        return _erreur("jeton_invalide", 401)

    donnees = _json(request)
    if not isinstance(donnees, dict):
        return _erreur("json_invalide")

    try:
        id_client = uuid.UUID(str(donnees.get("id_client")))
    except (TypeError, ValueError, AttributeError):
        return _erreur("id_client_invalide")

    question_uid = donnees.get("question_uid")
    if not isinstance(question_uid, str) or not question_uid.strip():
        return _erreur("question_uid_invalide")

    choix = donnees.get("choix")
    if not isinstance(choix, list) or not choix:
        return _erreur("choix_invalide")
    if any(not isinstance(lettre, str) for lettre in choix):
        return _erreur("choix_invalide")
    if len(set(choix)) != len(choix):
        return _erreur("choix_invalide")

    with transaction.atomic():
        session = (
            Session.objects.select_for_update()
            .select_related("quiz")
            .get(pk=participant.session_id)
        )
        maintenant = timezone.now()
        if session.statut != Session.STATUT_EN_COURS:
            return _erreur("seance_non_active", 409)
        if session.ends_at is None or maintenant > session.ends_at:
            return _erreur("temps_ecoule", 409)

        if Answer.objects.filter(id_client=id_client).exists():
            return JsonResponse(
                {
                    "ok": True,
                    "recu": True,
                    "deja": True,
                    "id_client": str(id_client),
                }
            )

        questions = services.questions_de_l_etape(
            session, session.etape_courante
        )
        question = next(
            (candidat for candidat in questions if candidat.uid == question_uid),
            None,
        )
        if question is None:
            return _erreur("question_inconnue", 404)
        question = (
            Question.objects.filter(pk=question.pk)
            .prefetch_related("choices")
            .first()
        )

        cible = services.question_courante_pour(session, participant)
        if cible is None or cible.pk != question.pk:
            return _erreur("mauvaise_question", 409)

        lettres = {choix_possible.lettre for choix_possible in question.choices.all()}
        if not set(choix).issubset(lettres):
            return _erreur("choix_invalide")

        if Answer.objects.filter(participant=participant, question=question).exists():
            return _erreur("deja_repondu", 409)

        try:
            with transaction.atomic():
                Answer.objects.create(
                    session=session,
                    participant=participant,
                    question=question,
                    choix_selectionnes=choix,
                    source=Answer.SOURCE_APP,
                    id_client=id_client,
                )
        except IntegrityError:
            if Answer.objects.filter(id_client=id_client).exists():
                return JsonResponse(
                    {
                        "ok": True,
                        "recu": True,
                        "deja": True,
                        "id_client": str(id_client),
                    }
                )
            return _erreur("deja_repondu", 409)

    return JsonResponse({"ok": True, "recu": True, "id_client": str(id_client)})


@login_required
@require_GET
def etat_participants(request):
    """État de la page participants (prof propriétaire uniquement).

    Ne renvoie jamais de PIN, de hash, d'énoncé, de texte de choix ni de
    réponse d'élève.
    """
    code = str(request.GET.get("code") or "").strip().upper()
    session = get_object_or_404(
        Session.objects.select_related("quiz", "groupe"),
        code_session=code,
    )
    if session.quiz.proprietaire_id != request.user.pk:
        raise PermissionDenied("Cette séance ne vous appartient pas.")
    return JsonResponse(services.etat_participants(session))


def _questions_prof(session: Session) -> list[dict]:
    if session.statut not in (
        Session.STATUT_EN_COURS,
        Session.STATUT_PAUSE,
    ):
        return []
    questions = services.questions_de_l_etape(session, session.etape_courante)
    if not questions:
        return []
    compteurs = services.compter_reponses_par_question(session, questions)
    resultat = []
    for question in questions:
        resultat.append(
            {
                "id": question.pk,
                "uid": question.uid,
                "enonce": question.enonce,
                "type": question.type,
                "image": question.image.url if question.image else None,
                "couleur": _couleur_question(question),
                "nb_reponses": compteurs.get(question.pk, 0),
                "choix": [
                    {
                        "lettre": choix.lettre,
                        "texte": choix.texte,
                        "est_correct": choix.est_correct,
                        "position": choix.position,
                    }
                    for choix in question.choices.all()
                ],
            }
        )
    return resultat


@login_required
@require_GET
def etat_prof(request):
    code = str(request.GET.get("code") or "").strip().upper()
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code,
        quiz__proprietaire=request.user,
    )
    session = services.avancer_si_necessaire(session)
    questions = _questions_prof(session)
    nb_reponses_etape = sum(q["nb_reponses"] for q in questions)
    return JsonResponse(
        {
            "ok": True,
            "code": session.code_session,
            "statut": session.statut,
            "etape": session.etape_courante,
            "nb_etapes": services.nombre_etapes(session),
            "temps_restant_s": services.temps_restant_s(session),
            "ends_at": session.ends_at.isoformat() if session.ends_at else None,
            "nb_participants": session.participants.count(),
            "nb_reponses": session.answers.count(),
            "nb_reponses_etape": nb_reponses_etape,
            "questions": questions,
        }
    )


@login_required
@require_POST
def piloter(request):
    donnees = _json(request)
    if not isinstance(donnees, dict):
        return _erreur("json_invalide")
    code = str(donnees.get("code") or "").strip().upper()
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code,
        quiz__proprietaire=request.user,
    )
    action = donnees.get("action")
    try:
        if action == "demarrer":
            session = services.demarrer_session(session)
        elif action == "pause":
            session = services.mettre_en_pause(session)
        elif action == "reprendre":
            session = services.reprendre(session)
        elif action == "plus_temps":
            session = services.ajouter_temps(session, donnees.get("delta"))
        elif action == "suivant":
            session = services.etape_suivante(session)
        elif action == "precedent":
            session = services.etape_precedente(session)
        elif action == "terminer":
            session = services.terminer_session(session)
        else:
            return _erreur("action_inconnue")
    except services.ErreurPilotage as exc:
        return _erreur(str(exc), 409)

    return JsonResponse(
        {
            "ok": True,
            "statut": session.statut,
            "etape": session.etape_courante,
            "temps_restant_s": services.temps_restant_s(session),
        }
    )

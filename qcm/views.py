"""Pages HTML : accueil, connexion élève, tableau et création de séance."""

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from qcm import services
from qcm.couleurs import infos_couleur
from qcm.models import Groupe, Participant, Quiz, Session
from qcm.resultats import calculer_resultats


def _session_prof(request, code: str) -> Session:
    """Séance du professeur connecté, ou 403 si elle appartient à un autre."""
    session = get_object_or_404(
        Session.objects.select_related("quiz", "groupe"),
        code_session=code.strip().upper(),
    )
    if session.quiz.proprietaire_id != request.user.pk:
        raise PermissionDenied("Cette séance ne vous appartient pas.")
    return session


def accueil(request):
    return render(request, "qcm/accueil.html")


def rejoindre_saisie(request):
    return render(request, "qcm/rejoindre_saisie.html")


def rejoindre(request, code: str):
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code.strip().upper(),
    )
    return render(request, "qcm/rejoindre.html", {"session": session})


def eleve(request, code: str):
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code.strip().upper(),
    )
    return render(request, "qcm/eleve.html", {"session": session})


@login_required
def tableau(request, code: str):
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code.strip().upper(),
        quiz__proprietaire=request.user,
    )
    session = services.avancer_si_necessaire(session)

    cartes = []
    nb_reponses_etape = 0
    if session.statut in (Session.STATUT_EN_COURS, Session.STATUT_PAUSE):
        etape = session.quiz.steps.filter(numero=session.etape_courante).first()
        if etape is not None:
            questions = list(
                etape.questions.prefetch_related("choices").order_by("ordre", "id")
            )
            compteurs = services.compter_reponses_par_question(session, questions)
            cartes = [
                {
                    "question": question,
                    "couleur": infos_couleur(question.couleur_slot),
                    "nb_reponses": compteurs.get(question.pk, 0),
                }
                for question in questions
            ]
            nb_reponses_etape = sum(compteurs.values())

    url_rejoindre = None
    qr_svg = None
    if session.statut == Session.STATUT_ATTENTE:
        url_rejoindre = services.construire_url_rejoindre(request, session)
        qr_svg = services.generer_qr_svg(url_rejoindre)

    contexte = {
        "session": session,
        "cartes": cartes,
        "nb_etapes": session.quiz.steps.count(),
        "nb_participants": session.participants.count(),
        "nb_reponses": session.answers.count(),
        "nb_reponses_etape": nb_reponses_etape,
        "temps_restant_s": services.temps_restant_s(session),
        "url_rejoindre": url_rejoindre,
        "qr_svg": qr_svg,
    }
    return render(request, "qcm/tableau.html", contexte)


@login_required
def session_creer(request):
    """Création d'une séance par le professeur, avec choix de son QCM et groupe."""
    quizzes = Quiz.objects.filter(proprietaire=request.user).order_by("titre")
    groupes = Groupe.objects.filter(proprietaire=request.user).order_by("nom")
    if request.method == "POST":
        quiz = get_object_or_404(
            Quiz,
            pk=request.POST.get("quiz"),
            proprietaire=request.user,
        )
        groupe = None
        groupe_id = request.POST.get("groupe")
        if groupe_id:
            groupe = get_object_or_404(
                Groupe,
                pk=groupe_id,
                proprietaire=request.user,
            )
        session = Session.objects.create(quiz=quiz, groupe=groupe)
        return redirect("qcm:session_initiale", code=session.code_session)
    return render(
        request,
        "qcm/session_creer.html",
        {"quizzes": quizzes, "groupes": groupes},
    )


@login_required
def session_initiale(request, code: str):
    """Page initiale d'une séance : code et QR code, uniquement ici."""
    session = _session_prof(request, code)
    url_rejoindre = services.construire_url_rejoindre(request, session)
    return render(
        request,
        "qcm/session_initiale.html",
        {
            "session": session,
            "url_rejoindre": url_rejoindre,
            "qr_svg": services.generer_qr_svg(url_rejoindre),
        },
    )


@login_required
def participants(request, code: str):
    """Liste du groupe de la séance, avec connexions en direct (polling)."""
    session = _session_prof(request, code)
    etat = services.etat_participants(session)
    return render(
        request,
        "qcm/participants.html",
        {"session": session, "etat": etat},
    )


@login_required
def resultats(request, code: str):
    """Notes par élève et taux de réussite par question, calculés à la volée."""
    session = _session_prof(request, code)
    donnees = calculer_resultats(session)
    return render(
        request,
        "qcm/resultats.html",
        {"session": session, **donnees},
    )


@login_required
@require_POST
def reinitialiser_appareil(request, code: str, participant_id: int):
    """Libère l'appareil d'un élève : son ancien jeton ne répondra plus."""
    session = _session_prof(request, code)
    participant = get_object_or_404(
        Participant,
        pk=participant_id,
        session=session,
    )
    participant.jeton_appareil = uuid.uuid4()
    participant.save(update_fields=["jeton_appareil"])
    messages.success(
        request,
        f"Appareil réinitialisé pour {participant}. L'élève doit se reconnecter.",
    )
    return redirect("qcm:participants", code=session.code_session)

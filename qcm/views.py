"""Pages HTML : accueil, connexion élève, tableau et création de séance."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from qcm import services
from qcm.couleurs import infos_couleur
from qcm.models import Quiz, Session


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

    contexte = {
        "session": session,
        "cartes": cartes,
        "nb_etapes": session.quiz.steps.count(),
        "nb_participants": session.participants.count(),
        "nb_reponses": session.answers.count(),
        "nb_reponses_etape": nb_reponses_etape,
        "temps_restant_s": services.temps_restant_s(session),
    }
    return render(request, "qcm/tableau.html", contexte)


@login_required
def session_creer(request):
    """Création d'une séance par le professeur, avec choix de son QCM."""
    quizzes = Quiz.objects.filter(proprietaire=request.user).order_by("titre")
    if request.method == "POST":
        quiz = get_object_or_404(
            Quiz,
            pk=request.POST.get("quiz"),
            proprietaire=request.user,
        )
        session = Session.objects.create(quiz=quiz)
        return redirect("qcm:session_initiale", code=session.code_session)
    return render(request, "qcm/session_creer.html", {"quizzes": quizzes})


@login_required
def session_initiale(request, code: str):
    """Page initiale d'une séance : code et QR code, uniquement ici."""
    session = get_object_or_404(
        Session.objects.select_related("quiz"),
        code_session=code.strip().upper(),
        quiz__proprietaire=request.user,
    )
    url_rejoindre = request.build_absolute_uri(
        reverse("qcm:rejoindre", args=[session.code_session])
    )
    return render(
        request,
        "qcm/session_initiale.html",
        {
            "session": session,
            "url_rejoindre": url_rejoindre,
            "qr_svg": services.generer_qr_svg(url_rejoindre),
        },
    )

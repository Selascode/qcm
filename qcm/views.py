"""Pages HTML : accueil, connexion élève et tableau professeur."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from qcm import services
from qcm.couleurs import infos_couleur
from qcm.models import Session


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

    url_rejoindre = request.build_absolute_uri(
        reverse("qcm:rejoindre", args=[session.code_session])
    )
    contexte = {
        "session": session,
        "cartes": cartes,
        "nb_etapes": session.quiz.steps.count(),
        "nb_participants": session.participants.count(),
        "nb_reponses": session.answers.count(),
        "nb_reponses_etape": nb_reponses_etape,
        "temps_restant_s": services.temps_restant_s(session),
        "url_rejoindre": url_rejoindre,
        "qr_svg": services.generer_qr_svg(url_rejoindre),
    }
    return render(request, "qcm/tableau.html", contexte)

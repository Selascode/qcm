"""Pages HTML : accueil, connexion élève, tableau et création de séance."""

import csv
import io
import json
import tempfile
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from qcm import services
from qcm.couleurs import infos_couleur
from qcm.import_participants import (
    ErreurImportParticipants,
    charger_fichier,
    importer_participants,
)
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


def _cartes_etape(session: Session) -> tuple[list, int]:
    """Cartes de la question courante et nombre de réponses de l'étape."""
    cartes = []
    nb_reponses_etape = 0
    if session.statut in (Session.STATUT_EN_COURS, Session.STATUT_PAUSE):
        questions = services.questions_de_l_etape(
            session, session.etape_courante
        )
        if questions:
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
    return cartes, nb_reponses_etape


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

    cartes, nb_reponses_etape = _cartes_etape(session)

    url_rejoindre = None
    qr_svg = None
    if session.statut == Session.STATUT_ATTENTE:
        url_rejoindre = services.construire_url_rejoindre(request, session)
        qr_svg = services.generer_qr_svg(url_rejoindre)

    contexte = {
        "session": session,
        "cartes": cartes,
        "nb_etapes": services.nombre_etapes(session),
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
    """Page initiale d'une séance : code, QR code et liens de la séance."""
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


@login_required
def presentation(request, code: str):
    """Vue plein écran : questions, timer et compteurs, sans aucun contrôle."""
    session = _session_prof(request, code)
    session = services.avancer_si_necessaire(session)
    cartes, nb_reponses_etape = _cartes_etape(session)
    return render(
        request,
        "qcm/presentation.html",
        {
            "session": session,
            "cartes": cartes,
            "nb_etapes": services.nombre_etapes(session),
            "nb_participants": session.participants.count(),
            "nb_reponses": session.answers.count(),
            "nb_reponses_etape": nb_reponses_etape,
            "temps_restant_s": services.temps_restant_s(session),
        },
    )


@login_required
def importer_eleves(request, groupe_id: int):
    """Import CSV/JSON d'élèves dans un groupe, avec export des identifiants."""
    groupe = get_object_or_404(
        Groupe.objects.select_related("proprietaire"),
        pk=groupe_id,
        proprietaire=request.user,
    )
    resultats = []
    if request.method == "POST":
        fichier = request.FILES.get("fichier")
        if fichier is None:
            messages.error(request, "Choisissez un fichier CSV ou JSON.")
        else:
            suffixe = Path(fichier.name).suffix.lower()
            if suffixe not in (".csv", ".json"):
                messages.error(
                    request,
                    "Format non reconnu : utilisez un fichier .csv ou .json.",
                )
            else:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffixe
                ) as tampon:
                    for bloc in fichier.chunks():
                        tampon.write(bloc)
                    chemin = Path(tampon.name)
                try:
                    lignes = charger_fichier(chemin)
                    resultats = importer_participants(lignes, groupe)
                    messages.success(
                        request,
                        f"{len(resultats)} élève(s) importé(s) dans "
                        f"« {groupe.nom} ».",
                    )
                except ErreurImportParticipants as exc:
                    for message in exc.messages:
                        messages.error(request, message)
                finally:
                    chemin.unlink(missing_ok=True)
    return render(
        request,
        "qcm/importer_eleves.html",
        {"groupe": groupe, "resultats": resultats},
    )


@login_required
def exporter_identifiants(request, groupe_id: int, format: str):
    """Export CSV/JSON des identifiants d'un groupe (sans PIN)."""
    groupe = get_object_or_404(Groupe, pk=groupe_id, proprietaire=request.user)
    eleves = groupe.etudiants.order_by("nom", "prenom")
    if format == "json":
        contenu = json.dumps(
            [
                {
                    "nom": student.nom,
                    "prenom": student.prenom,
                    "code_etudiant": student.code_etudiant,
                }
                for student in eleves
            ],
            ensure_ascii=False,
            indent=2,
        )
        content_type = "application/json"
        extension = "json"
    elif format == "csv":
        tampon = io.StringIO()
        redacteur = csv.writer(tampon)
        redacteur.writerow(["nom", "prenom", "code_etudiant"])
        for student in eleves:
            redacteur.writerow(
                [student.nom, student.prenom, student.code_etudiant]
            )
        contenu = tampon.getvalue()
        content_type = "text/csv"
        extension = "csv"
    else:
        raise Http404("Format d'export inconnu.")

    reponse = HttpResponse(
        contenu,
        content_type=f"{content_type}; charset=utf-8",
    )
    reponse["Content-Disposition"] = (
        f'attachment; filename="identifiants_{slugify(groupe.nom)}.{extension}"'
    )
    return reponse

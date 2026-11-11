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
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from qcm import import_questions, services
from qcm.appareil import NOM_COOKIE_APPAREIL
from qcm.couleurs import infos_couleur
from qcm.exports import exporter_detail_csv, exporter_notes_csv
from qcm.import_papier import (
    ErreurImportPapier,
    analyser_reponses,
    importer_reponses,
    trouver_etudiant,
)
from qcm.import_participants import (
    ErreurImportParticipants,
    charger_fichier,
    importer_participants,
)
from qcm.models import (
    Answer,
    Groupe,
    Participant,
    Question,
    QuestionSet,
    Quiz,
    Session,
    Student,
)
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
                    "couleur": infos_couleur(position),
                    "nb_reponses": compteurs.get(question.pk, 0),
                }
                for position, question in enumerate(questions, start=1)
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


def _reponse_csv(contenu: str, nom_fichier: str) -> HttpResponse:
    reponse = HttpResponse(contenu, content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    return reponse


@login_required
def exporter_resultats_notes(request, code: str):
    """Export CSV des notes par élève, avec une colonne par question."""
    session = _session_prof(request, code)
    contenu = exporter_notes_csv(session)  # BOM UTF-8 et virgule
    return _reponse_csv(
        contenu, f"notes_{session.code_session}.csv"
    )


@login_required
def exporter_resultats_detail(request, code: str):
    """Export CSV du détail par élève et par question."""
    session = _session_prof(request, code)
    contenu = exporter_detail_csv(session)  # BOM UTF-8 et virgule
    return _reponse_csv(
        contenu, f"detail_{session.code_session}.csv"
    )


def _eleve_demande(request):
    valeur = request.POST.get("eleve") or request.GET.get("eleve")
    if not valeur or not str(valeur).isdigit():
        return None
    return Student.objects.filter(pk=int(valeur)).first()


def _options_eleves(session, eleve, participant):
    """Élèves proposés dans la liste, avec leur participant éventuel."""
    if session.groupe_id:
        etudiants = list(
            Student.objects.filter(groupe_id=session.groupe_id).order_by(
                "nom", "prenom"
            )
        )
    else:
        etudiants = list(Student.objects.all().order_by("nom", "prenom"))

    participants = {
        lien.student_id: lien
        for lien in session.participants.filter(student__isnull=False)
    }
    options = [
        {"student": etudiant, "participant": participants.get(etudiant.pk)}
        for etudiant in etudiants
    ]
    if eleve is not None and all(
        option["student"].pk != eleve.pk for option in options
    ):
        options.append({"student": eleve, "participant": participant})
        options.sort(
            key=lambda option: (
                option["student"].nom.casefold(),
                option["student"].prenom.casefold(),
            )
        )
    return options


def _lignes_papier(participant, questions):
    """Questions du QCM avec la réponse existante du participant, le cas échéant."""
    reponses = {}
    if participant is not None:
        reponses = {
            reponse.question_id: reponse
            for reponse in Answer.objects.filter(participant=participant)
        }
    lignes = []
    for question in questions:
        reponse = reponses.get(question.pk)
        lignes.append(
            {
                "question": question,
                "reponse": reponse,
                "choix": reponse.choix_selectionnes if reponse else [],
                "source": reponse.source if reponse else None,
                "est_app": (
                    reponse is not None
                    and reponse.source == Answer.SOURCE_APP
                ),
            }
        )
    return lignes


def _url_saisie_papier(session, eleve=None):
    url = reverse("qcm:saisie_papier", args=[session.code_session])
    if eleve is not None:
        return f"{url}?eleve={eleve.pk}"
    return url


def _lier_eleve_papier(request, session):
    identifiant = (request.POST.get("identifiant") or "").strip()
    if not identifiant:
        messages.error(request, "Saisissez un identifiant.")
        return None
    etudiant = trouver_etudiant(identifiant)
    if etudiant is None:
        messages.error(
            request,
            f"Aucun élève avec l'identifiant « {identifiant} ».",
        )
        return None

    participant = Participant.objects.filter(
        session=session, student=etudiant
    ).first()
    if participant is None:
        Participant.objects.create(
            session=session,
            student=etudiant,
            couleur_assignee=services.prochaine_couleur(session),
        )
        messages.success(
            request,
            f"{etudiant.prenom} {etudiant.nom} lié à la séance.",
        )
    else:
        messages.info(
            request,
            f"{etudiant.prenom} {etudiant.nom} était déjà lié à la séance.",
        )
    if session.groupe_id and etudiant.groupe_id != session.groupe_id:
        messages.info(
            request,
            "Cet élève n'appartient pas au groupe de la séance.",
        )
    return redirect(_url_saisie_papier(session, etudiant))


def _enregistrer_reponses_papier(request, session, questions):
    eleve = _eleve_demande(request)
    if eleve is None:
        messages.error(request, "Choisissez un élève.")
        return None

    selections = {}
    erreurs = []
    for question in questions:
        valeurs = [
            valeur.strip()
            for valeur in request.POST.getlist(f"q_{question.pk}")
            if valeur.strip()
        ]
        if not valeurs:
            continue
        valeurs = list(dict.fromkeys(valeurs))
        disponibles = {
            choix.lettre for choix in question.choices.all()
        }
        if not set(valeurs).issubset(disponibles):
            erreurs.append(f"{question.uid} : lettre inconnue.")
        elif (
            question.type == Question.TYPE_UNIQUE and len(valeurs) > 1
        ):
            erreurs.append(
                f"{question.uid} : une seule lettre attendue."
            )
        else:
            selections[question.pk] = valeurs

    if erreurs:
        for erreur in erreurs:
            messages.error(request, erreur)
        return None

    with transaction.atomic():
        participant = Participant.objects.filter(
            session=session, student=eleve
        ).first()
        if participant is None:
            participant = Participant.objects.create(
                session=session,
                student=eleve,
                couleur_assignee=services.prochaine_couleur(session),
            )
        existantes = {
            reponse.question_id: reponse
            for reponse in Answer.objects.filter(
                participant=participant
            ).select_for_update()
        }
        creees = mises_a_jour = ignorees = 0
        for question in questions:
            reponse = existantes.get(question.pk)
            selection = selections.get(question.pk)
            if reponse is not None:
                if reponse.source == Answer.SOURCE_APP:
                    ignorees += 1
                    continue
                if (
                    selection is not None
                    and reponse.choix_selectionnes != selection
                ):
                    reponse.choix_selectionnes = selection
                    reponse.save(update_fields=["choix_selectionnes"])
                    mises_a_jour += 1
                continue
            if selection is None:
                continue
            Answer.objects.create(
                session=session,
                participant=participant,
                question=question,
                choix_selectionnes=selection,
                source=Answer.SOURCE_PAPIER,
                id_client=uuid.uuid4(),
            )
            creees += 1

    messages.success(
        request,
        f"{creees} réponse(s) papier enregistrée(s), "
        f"{mises_a_jour} mise(s) à jour, "
        f"{ignorees} réponse(s) de l'application conservée(s).",
    )
    return redirect(_url_saisie_papier(session, eleve))


def _importer_reponses_papier(request, session):
    fichier = request.FILES.get("fichier")
    if fichier is None:
        messages.error(request, "Choisissez un fichier CSV.")
        return None
    if Path(fichier.name).suffix.lower() != ".csv":
        messages.error(
            request, "Format non reconnu : utilisez un fichier .csv."
        )
        return None
    try:
        contenu = fichier.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        messages.error(request, "Le fichier doit être encodé en UTF-8.")
        return None

    try:
        lignes = analyser_reponses(contenu)
        compteurs = importer_reponses(lignes, session)
    except ErreurImportPapier as exc:
        for message in exc.messages:
            messages.error(request, message)
        return None

    messages.success(
        request,
        f"{compteurs['creees']} réponse(s) papier créée(s), "
        f"{compteurs['mises_a_jour']} mise(s) à jour, "
        f"{compteurs['ignorees_app']} ignorée(s) car réponse application, "
        f"{compteurs['participants_crees']} participant(s) créé(s).",
    )
    return redirect(_url_saisie_papier(session, _eleve_demande(request)))


@login_required
def saisie_papier(request, code: str):
    """Saisie groupée des réponses papier d'un élève, ou import CSV."""
    session = _session_prof(request, code)
    questions = services.questions_du_quiz(session.quiz)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "lier":
            redirection = _lier_eleve_papier(request, session)
        elif action == "enregistrer":
            redirection = _enregistrer_reponses_papier(
                request, session, questions
            )
        elif action == "importer":
            redirection = _importer_reponses_papier(request, session)
        else:
            messages.error(request, "Action inconnue.")
            redirection = None
        if redirection is not None:
            return redirection

    eleve = _eleve_demande(request)
    participant = None
    if eleve is not None:
        participant = Participant.objects.filter(
            session=session, student=eleve
        ).first()

    return render(
        request,
        "qcm/saisie_papier.html",
        {
            "session": session,
            "eleve": eleve,
            "participant": participant,
            "eleves": _options_eleves(session, eleve, participant),
            "lignes": _lignes_papier(participant, questions),
        },
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
    participant.jeton_appareil = None
    participant.cookie_appareil = None
    participant.save(update_fields=["jeton_appareil", "cookie_appareil"])
    messages.success(
        request,
        f"Appareil libéré pour {participant}. L'élève doit se reconnecter.",
    )
    reponse = redirect("qcm:participants", code=session.code_session)
    reponse.delete_cookie(NOM_COOKIE_APPAREIL)
    return reponse


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
def importer_questions(request, set_id: int):
    """Import JSON/CSV de questions dans un ensemble de la banque."""
    sets = QuestionSet.objects.filter(proprietaire=request.user).order_by("nom")
    question_set = get_object_or_404(sets, pk=set_id)
    resultats = []
    if request.method == "POST":
        set_choisi = request.POST.get("set")
        if set_choisi:
            question_set = get_object_or_404(sets, pk=set_choisi)
        fichier = request.FILES.get("fichier")
        if fichier is None:
            messages.error(request, "Choisissez un fichier JSON ou CSV.")
        else:
            suffixe = Path(fichier.name).suffix.lower()
            if suffixe not in (".json", ".csv"):
                messages.error(
                    request,
                    "Format non reconnu : utilisez un fichier .json ou .csv.",
                )
            else:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffixe
                ) as tampon:
                    for bloc in fichier.chunks():
                        tampon.write(bloc)
                    chemin = Path(tampon.name)
                try:
                    donnees = import_questions.charger_fichier_questions(chemin)
                    resultats = import_questions.importer_questions(donnees, question_set)
                    messages.success(
                        request,
                        f"{len(resultats)} question(s) importée(s) dans "
                        f"« {question_set.nom} ».",
                    )
                except import_questions.ErreurImport as exc:
                    for message in exc.messages:
                        messages.error(request, message)
                finally:
                    chemin.unlink(missing_ok=True)
    return render(
        request,
        "qcm/importer_questions.html",
        {
            "question_set": question_set,
            "sets": sets,
            "resultats": resultats,
        },
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

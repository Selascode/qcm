"""Admin Django : banque de questions, sélection et consultation des QCM."""

import uuid

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from qcm.models import (
    Answer,
    Choice,
    Groupe,
    Participant,
    Question,
    QuestionSet,
    Quiz,
    QuizQuestion,
    Session,
    Student,
)

admin.site.site_header = "QCM en direct"
admin.site.site_title = "QCM en direct"
admin.site.index_title = "Administration"


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ("lettre", "texte", "est_correct", "position")
    ordering = ("position",)


class QuestionInline(admin.TabularInline):
    """Questions d'un ensemble, éditables depuis la page du set."""

    model = Question
    extra = 0
    fields = ("uid", "enonce", "type", "duree_s", "ordre")
    ordering = ("ordre", "uid")
    verbose_name = "Question"
    verbose_name_plural = "Questions"


@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "proprietaire",
        "nb_questions",
        "lien_import",
        "date_creation",
    )
    list_filter = ("proprietaire",)
    search_fields = ("nom",)
    inlines = (QuestionInline,)
    readonly_fields = ("lien_import",)

    @admin.display(description="Questions")
    def nb_questions(self, obj: QuestionSet) -> int:
        return obj.questions.count()

    @admin.display(description="Import")
    def lien_import(self, obj: QuestionSet) -> str:
        if not obj or not obj.pk:
            return "Enregistrez l'ensemble pour importer des questions."
        url = reverse("qcm:importer_questions", args=[obj.pk])
        return format_html('<a href="{}">Importer</a>', url)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("uid", "set", "type", "duree_s", "ordre")
    list_filter = ("set__proprietaire", "set", "type")
    search_fields = ("uid", "enonce", "set__nom")
    inlines = (ChoiceInline,)
    list_select_related = ("set",)
    fields = (
        "set",
        "uid",
        "enonce",
        "image",
        "type",
        "afficher_indice_multiple",
        "duree_s",
        "ordre",
    )


class QuizQuestionInline(admin.TabularInline):
    """Sélection courante, en lecture seule, retirable depuis la page du QCM."""

    model = QuizQuestion
    extra = 0
    fields = ("position", "question")
    readonly_fields = ("position", "question")
    ordering = ("position", "id")
    can_delete = True
    verbose_name = "Question sélectionnée"
    verbose_name_plural = "Questions sélectionnées"

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "proprietaire",
        "penalite_active",
        "facteur_penalite",
        "duree_s",
        "nb_questions",
        "lien_selection",
    )
    list_filter = ("proprietaire", "penalite_active")
    search_fields = ("titre",)
    inlines = (QuizQuestionInline,)
    readonly_fields = ("lien_selection",)
    fields = (
        "titre",
        "proprietaire",
        "penalite_active",
        "facteur_penalite",
        "duree_s",
        "lien_selection",
    )

    @admin.display(description="Questions")
    def nb_questions(self, obj: Quiz) -> int:
        return obj.questions.count()

    @admin.display(description="Sélection")
    def lien_selection(self, obj: Quiz) -> str:
        if not obj or not obj.pk:
            return "Enregistrez le QCM pour sélectionner des questions."
        url = reverse("admin:qcm_quiz_selection", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Sélectionner les questions</a>',
            url,
        )

    def get_urls(self):
        urls = super().get_urls()
        personnalisees = [
            path(
                "<int:quiz_id>/selection/",
                self.admin_site.admin_view(self.selection_view),
                name="qcm_quiz_selection",
            ),
        ]
        return personnalisees + urls

    def selection_view(self, request, quiz_id: int):
        quiz = get_object_or_404(
            Quiz.objects.select_related("proprietaire"),
            pk=quiz_id,
        )
        if not self.has_change_permission(request, quiz):
            raise PermissionDenied("Vous ne pouvez pas modifier ce QCM.")
        if (
            quiz.proprietaire_id != request.user.pk
            and not request.user.is_superuser
        ):
            raise PermissionDenied("Ce QCM ne vous appartient pas.")

        if request.method == "POST":
            self._traiter_panier(request, quiz)
            return redirect("admin:qcm_quiz_selection", quiz_id=quiz.pk)

        sets = (
            QuestionSet.objects.filter(proprietaire=quiz.proprietaire)
            .prefetch_related("questions")
            .order_by("nom")
        )
        selection = list(
            quiz.quiz_questions.select_related(
                "question", "question__set"
            ).order_by("position", "id")
        )
        contexte = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": quiz,
            "title": f"Sélectionner les questions — {quiz.titre}",
            "sets": sets,
            "selection": selection,
            "selection_ids": {ligne.question_id for ligne in selection},
        }
        return render(request, "admin/qcm/quiz/selection.html", contexte)

    def _traiter_panier(self, request, quiz: Quiz) -> None:
        action = request.POST.get("action")
        if action == "ajouter":
            identifiants = []
            for valeur in request.POST.getlist("questions"):
                if str(valeur).isdigit():
                    identifiants.append(int(valeur))
            questions = Question.objects.filter(
                pk__in=identifiants,
                set__proprietaire=quiz.proprietaire,
            )
            par_identifiant = {question.pk: question for question in questions}
            deja_presents = set(
                quiz.quiz_questions.values_list("question_id", flat=True)
            )
            position = (
                quiz.quiz_questions.aggregate(maximum=Max("position"))["maximum"]
                or 0
            )
            ajoutees = 0
            with transaction.atomic():
                for identifiant in dict.fromkeys(identifiants):
                    if (
                        identifiant in deja_presents
                        or identifiant not in par_identifiant
                    ):
                        continue
                    position += 1
                    QuizQuestion.objects.create(
                        quiz=quiz,
                        question=par_identifiant[identifiant],
                        position=position,
                    )
                    ajoutees += 1
            if ajoutees:
                messages.success(
                    request,
                    f"{ajoutees} question(s) ajoutée(s) à « {quiz.titre} ».",
                )
            else:
                messages.info(request, "Aucune nouvelle question à ajouter.")
        elif action == "retirer":
            identifiant = request.POST.get("question")
            if str(identifiant).isdigit():
                with transaction.atomic():
                    quiz.quiz_questions.filter(
                        question_id=int(identifiant)
                    ).delete()
                    for position, ligne in enumerate(
                        quiz.quiz_questions.order_by("position", "id"),
                        start=1,
                    ):
                        if ligne.position != position:
                            ligne.position = position
                            ligne.save(update_fields=["position"])
                messages.success(request, "Question retirée du QCM.")
        else:
            messages.error(request, "Action inconnue.")


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("question", "lettre", "texte", "est_correct", "position")
    list_filter = ("est_correct",)
    search_fields = ("question__uid", "texte")


class StudentInline(admin.TabularInline):
    """Ajout/modification/suppression des élèves depuis la page du groupe."""

    model = Student
    extra = 1
    fields = ("nom", "prenom", "code_etudiant", "identifiant_insa")
    readonly_fields = ("code_etudiant",)
    ordering = ("nom", "prenom")
    verbose_name = "Élève"
    verbose_name_plural = "Élèves"


@admin.register(Groupe)
class GroupeAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "proprietaire",
        "nb_etudiants",
        "lien_import",
        "date_creation",
    )
    list_filter = ("proprietaire",)
    search_fields = ("nom",)
    inlines = (StudentInline,)

    @admin.display(description="Élèves")
    def nb_etudiants(self, obj: Groupe) -> int:
        return obj.etudiants.count()

    @admin.display(description="Import")
    def lien_import(self, obj: Groupe) -> str:
        url = reverse("qcm:importer_eleves", args=[obj.pk])
        return format_html('<a href="{}">Importer</a>', url)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "prenom",
        "code_etudiant",
        "identifiant_insa",
        "groupe",
    )
    list_filter = ("groupe",)
    search_fields = ("nom", "prenom", "code_etudiant", "identifiant_insa")
    fields = (
        "nom",
        "prenom",
        "code_etudiant",
        "identifiant_insa",
        "groupe",
    )
    readonly_fields = ("code_etudiant",)
    list_select_related = ("groupe",)

    def has_add_permission(self, request) -> bool:
        # Les élèves s'ajoutent depuis l'inline de la page Groupe ; cette
        # entrée de menu reste en consultation (recherche, filtre).
        return False


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "code_session",
        "quiz",
        "groupe",
        "statut",
        "etape_courante",
        "ends_at",
        "lien_tableau",
        "lien_resultats",
    )
    list_filter = ("statut", "quiz", "groupe")
    search_fields = ("code_session", "quiz__titre")
    readonly_fields = (
        "code_session",
        "statut",
        "etape_courante",
        "ends_at",
        "reste_en_pause",
    )
    fields = (
        "quiz",
        "groupe",
        "code_session",
        "statut",
        "etape_courante",
        "ends_at",
        "reste_en_pause",
    )

    @admin.display(description="Tableau")
    def lien_tableau(self, obj: Session):
        if not obj.code_session:
            return "—"
        url = reverse("qcm:tableau", args=[obj.code_session])
        return format_html('<a href="{}" target="_blank">Ouvrir</a>', url)

    @admin.display(description="Résultats")
    def lien_resultats(self, obj: Session):
        if obj.statut not in (Session.STATUT_EN_COURS, Session.STATUT_FINI):
            return "—"
        url = reverse("qcm:resultats", args=[obj.code_session])
        return format_html(
            '<a href="{}">Voir les résultats</a>',
            url,
        )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "student",
        "groupe",
        "couleur_assignee",
        "symbole",
        "derniere_activite",
        "graine_melange",
    )
    list_filter = ("session",)
    search_fields = (
        "session__code_session",
        "student__nom",
        "student__prenom",
        "student__code_etudiant",
        "student__identifiant_insa",
    )
    list_select_related = ("student__groupe",)

    @admin.display(description="Groupe")
    def groupe(self, obj: Participant) -> str:
        if obj.student_id and obj.student.groupe_id:
            return obj.student.groupe.nom
        return "—"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class AnswerAdminForm(forms.ModelForm):
    """Saisie manuelle d'une réponse papier, sans écraser une réponse app."""

    class Meta:
        model = Answer
        fields = ("participant", "question", "choix_selectionnes", "source")

    def clean(self):
        cleaned = super().clean()
        participant = cleaned.get("participant")
        question = cleaned.get("question")
        choix = cleaned.get("choix_selectionnes")

        if participant and question:
            existante = Answer.objects.filter(
                participant=participant, question=question
            )
            if self.instance.pk:
                existante = existante.exclude(pk=self.instance.pk)
            reponse = existante.first()
            if reponse is not None:
                if reponse.source == Answer.SOURCE_APP:
                    raise forms.ValidationError(
                        "Une réponse de l'application existe déjà pour cet "
                        "élève et cette question : elle prime."
                    )
                raise forms.ValidationError(
                    "Une réponse existe déjà pour cet élève et cette question."
                )
            if not question.quiz_questions.filter(
                quiz=participant.session.quiz
            ).exists():
                raise forms.ValidationError(
                    "Cette question n'appartient pas au QCM de la séance de "
                    "cet élève."
                )

        if choix is not None:
            if (
                not isinstance(choix, list)
                or not choix
                or any(not isinstance(lettre, str) for lettre in choix)
            ):
                raise forms.ValidationError(
                    {
                        "choix_selectionnes": (
                            "Indiquez une liste non vide de lettres, par "
                            'exemple ["A"].'
                        )
                    }
                )
            if len(set(choix)) != len(choix):
                raise forms.ValidationError(
                    {"choix_selectionnes": "Une lettre est présente deux fois."}
                )
            if question is not None:
                lettres = set(
                    question.choices.values_list("lettre", flat=True)
                )
                if not set(choix).issubset(lettres):
                    raise forms.ValidationError(
                        {
                            "choix_selectionnes": (
                                "Une lettre ne correspond pas aux choix de "
                                "cette question."
                            )
                        }
                    )
                if (
                    question.type == Question.TYPE_UNIQUE
                    and len(choix) > 1
                ):
                    raise forms.ValidationError(
                        {
                            "choix_selectionnes": (
                                "Cette question n'admet qu'un seul choix."
                            )
                        }
                    )
        return cleaned


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    form = AnswerAdminForm
    list_display = (
        "participant",
        "question",
        "choix_selectionnes",
        "recu_a",
        "source",
        "id_client",
    )
    list_filter = ("source", "session")
    search_fields = ("participant__session__code_session", "question__uid")
    fields = ("participant", "question", "choix_selectionnes", "source")

    def get_changeform_initial_data(self, request) -> dict:
        donnees = super().get_changeform_initial_data(request)
        donnees.setdefault("source", Answer.SOURCE_PAPIER)
        return donnees

    def has_add_permission(self, request) -> bool:
        return True

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            if db_field.name == "participant":
                kwargs["queryset"] = Participant.objects.filter(
                    session__quiz__proprietaire=request.user
                )
            elif db_field.name == "question":
                kwargs["queryset"] = Question.objects.filter(
                    set__proprietaire=request.user
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change) -> None:
        if not obj.id_client:
            obj.id_client = uuid.uuid4()
        if obj.participant_id and not obj.session_id:
            obj.session_id = obj.participant.session_id
        super().save_model(request, obj, form, change)

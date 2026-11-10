"""Admin Django : saisie des QCM et consultation des séances."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from qcm.models import (
    Answer,
    Choice,
    Groupe,
    Participant,
    Question,
    Quiz,
    Session,
    Step,
    Student,
)

admin.site.site_header = "QCM en direct"
admin.site.site_title = "QCM en direct"
admin.site.index_title = "Administration"


class StepInline(admin.TabularInline):
    model = Step
    extra = 0
    ordering = ("numero",)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "proprietaire",
        "penalite_active",
        "facteur_penalite",
        "nb_etapes",
        "nb_questions",
    )
    list_filter = ("proprietaire", "penalite_active")
    search_fields = ("titre",)
    inlines = (StepInline,)

    @admin.display(description="Étapes")
    def nb_etapes(self, obj: Quiz) -> int:
        return obj.steps.count()

    @admin.display(description="Questions")
    def nb_questions(self, obj: Quiz) -> int:
        return obj.questions.count()


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = (
        "uid",
        "enonce",
        "image",
        "type",
        "afficher_indice_multiple",
        "ordre",
        "couleur_slot",
    )
    ordering = ("ordre",)


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ("quiz", "numero", "duree_s")
    list_filter = ("quiz",)
    ordering = ("quiz", "numero")
    inlines = (QuestionInline,)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ("lettre", "texte", "est_correct", "position")
    ordering = ("position",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("uid", "step", "type", "couleur_slot", "ordre")
    list_filter = ("step__quiz", "type", "couleur_slot")
    search_fields = ("uid", "enonce")
    inlines = (ChoiceInline,)
    fields = (
        "step",
        "uid",
        "enonce",
        "image",
        "type",
        "afficher_indice_multiple",
        "ordre",
        "couleur_slot",
    )


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("question", "lettre", "texte", "est_correct", "position")
    list_filter = ("est_correct",)
    search_fields = ("question__uid", "texte")


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

    @admin.display(description="Élèves")
    def nb_etudiants(self, obj: Groupe) -> int:
        return obj.etudiants.count()

    @admin.display(description="Import")
    def lien_import(self, obj: Groupe) -> str:
        url = reverse("qcm:importer_eleves", args=[obj.pk])
        return format_html('<a href="{}">Importer</a>', url)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "code_etudiant", "groupe")
    list_filter = ("groupe",)
    search_fields = ("nom", "prenom", "code_etudiant")
    fields = ("nom", "prenom", "code_etudiant", "groupe")
    readonly_fields = ("code_etudiant",)
    list_select_related = ("groupe",)

    def has_add_permission(self, request) -> bool:
        # Les élèves sont créés par ``import_participants`` (identifiant + PIN).
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


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
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

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

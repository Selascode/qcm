"""Modèle de données du QCM (V2).

Invariants respectés (AGENTS.md §3) :
- ``Answer`` a une contrainte unique ``(participant, question)`` ;
- ``Answer.source`` et ``Answer.id_client`` sont conservés ;
- ``Session.ends_at`` est la seule référence temporelle ;
- ``Participant.couleur_assignee`` et ``Participant.graine_melange`` sont persistés ;
- ``Question.uid`` est unique par quiz ;
- la durée est portée par ``Step``, pas par ``Question``.

V2 ajoute les groupes, les élèves identifiés (``Student``) et le barème
configurable par QCM. ``Session.groupe`` reste nullable pour la démo.
"""

import secrets
import unicodedata
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from qcm.couleurs import COULEURS, NB_COULEURS

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGUEUR_CODE = 6


def generer_code_session() -> str:
    """Code court, lisible, sans caractères ambigus (I, O, 0, 1)."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(LONGUEUR_CODE))


def tirer_couleur() -> int:
    """Ancien tirage aléatoire, conservé pour la migration 0001.

    La couleur réelle est désormais attribuée en Round-Robin à la connexion
    (``services.prochaine_couleur``) ; ce helper n'est plus utilisé par le
    modèle mais reste importable par les migrations historiques.
    """
    return secrets.randbelow(NB_COULEURS) + 1


def tirer_graine() -> int:
    return secrets.randbits(32)


def _normaliser_texte(texte: str) -> str:
    normalise = (
        unicodedata.normalize("NFKD", texte)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return "".join(
        caractere for caractere in normalise if caractere.isalnum()
    ).upper()


def valider_facteur_penalite(valeur: float) -> None:
    """Le facteur de pénalité doit être strictement positif."""
    if valeur is None or valeur <= 0:
        raise ValidationError(
            "Le facteur de pénalité doit être strictement positif."
        )


class Quiz(models.Model):
    titre = models.CharField("Titre", max_length=200)
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz",
        verbose_name="Propriétaire",
    )
    penalite_active = models.BooleanField(
        "Pénaliser les mauvaises réponses",
        default=True,
        help_text=(
            "Si cette case est décochée, une mauvaise réponse ne retire aucun "
            "point (elle contribue à 0)."
        ),
    )
    facteur_penalite = models.FloatField(
        "Facteur de pénalité",
        default=1.0,
        validators=[valider_facteur_penalite],
        help_text=(
            "Multiplicateur appliqué à chaque mauvaise réponse. Doit être "
            "strictement supérieur à 0."
        ),
    )

    class Meta:
        ordering = ("titre",)
        verbose_name = "QCM"
        verbose_name_plural = "QCM"

    def __str__(self) -> str:
        return self.titre


class Step(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name="QCM",
    )
    numero = models.PositiveSmallIntegerField(
        "Numéro",
        validators=[MinValueValidator(1)],
    )
    duree_s = models.PositiveIntegerField(
        "Durée (s)",
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ("numero",)
        verbose_name = "Étape"
        verbose_name_plural = "Étapes"
        constraints = (
            models.UniqueConstraint(
                fields=["quiz", "numero"],
                name="unique_step_numero_par_quiz",
            ),
        )

    def __str__(self) -> str:
        return f"Étape {self.numero} — {self.duree_s} s"


class Question(models.Model):
    TYPE_UNIQUE = "unique"
    TYPE_MULTIPLE = "multiple"
    TYPES = (
        (TYPE_UNIQUE, "Choix unique"),
        (TYPE_MULTIPLE, "Choix multiple"),
    )

    # FK dénormalisée : elle garantit l'unicité (quiz, uid) au niveau base,
    # que la hiérarchie Step→Question ne permettrait pas d'exprimer.
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        editable=False,
        verbose_name="QCM",
    )
    step = models.ForeignKey(
        Step,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Étape",
    )
    uid = models.CharField("Identifiant", max_length=64)
    enonce = models.TextField("Énoncé")
    image = models.FileField("Image", upload_to="questions/", blank=True)
    type = models.CharField(
        "Type",
        max_length=10,
        choices=TYPES,
        default=TYPE_UNIQUE,
    )
    afficher_indice_multiple = models.BooleanField(
        "Afficher l'indice choix multiple",
        default=False,
    )
    ordre = models.PositiveSmallIntegerField(
        "Ordre",
        validators=[MinValueValidator(1)],
        default=1,
    )
    couleur_slot = models.PositiveSmallIntegerField(
        "Emplacement couleur",
        validators=[MinValueValidator(1), MaxValueValidator(NB_COULEURS)],
        default=1,
    )

    class Meta:
        ordering = ("ordre",)
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        constraints = (
            models.UniqueConstraint(
                fields=["quiz", "uid"],
                name="unique_question_uid_par_quiz",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if self.step_id:
            try:
                etape = self.step
            except Step.DoesNotExist:
                etape = None
            if etape is not None:
                self.quiz = etape.quiz
                autres = Question.objects.filter(step_id=self.step_id)
                if self.pk:
                    autres = autres.exclude(pk=self.pk)
                if autres.count() >= 4:
                    raise ValidationError(
                        {"step": "Une étape ne peut pas contenir plus de 4 questions."}
                    )
        if self.quiz_id and self.uid:
            doublon = Question.objects.filter(quiz_id=self.quiz_id, uid=self.uid)
            if self.pk:
                doublon = doublon.exclude(pk=self.pk)
            if doublon.exists():
                raise ValidationError(
                    {"uid": "Cet identifiant de question existe déjà dans ce QCM."}
                )

    def save(self, *args, **kwargs) -> None:
        if self.step_id:
            self.quiz_id = self.step.quiz_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.uid} — {self.enonce[:60]}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name="Question",
    )
    lettre = models.CharField("Lettre", max_length=1)
    texte = models.TextField("Texte")
    est_correct = models.BooleanField("Correcte", default=False)
    position = models.PositiveSmallIntegerField("Position", default=0)

    class Meta:
        ordering = ("position",)
        verbose_name = "Choix"
        verbose_name_plural = "Choix"
        constraints = (
            models.UniqueConstraint(
                fields=["question", "lettre"],
                name="unique_choice_lettre_par_question",
            ),
        )

    def __str__(self) -> str:
        return f"{self.lettre}. {self.texte[:60]}"


class Groupe(models.Model):
    """Groupe d'élèves rattaché à un professeur (ex. « ISIA4 »)."""

    nom = models.CharField("Nom", max_length=100, unique=True)
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="groupes",
        verbose_name="Propriétaire",
    )
    date_creation = models.DateTimeField("Date de création", auto_now_add=True)

    class Meta:
        ordering = ("nom",)
        verbose_name = "Groupe"
        verbose_name_plural = "Groupes"

    def __str__(self) -> str:
        return self.nom


class Student(models.Model):
    """Élève identifié, rattaché à un groupe et à un seul."""

    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    code_etudiant = models.CharField(
        "Identifiant",
        max_length=32,
        unique=True,
        blank=True,
    )
    groupe = models.ForeignKey(
        Groupe,
        on_delete=models.PROTECT,
        related_name="etudiants",
        verbose_name="Groupe",
    )

    class Meta:
        ordering = ("nom", "prenom")
        verbose_name = "Élève (Base)"
        verbose_name_plural = "Élèves (Base)"

    @classmethod
    def generer_code_etudiant(cls, nom: str, prenom: str) -> str:
        """Identifiant lisible ``PRENOM-NOMnn`` (ex. ``MARIE-DUP32``), unique."""
        prenom_normalise = _normaliser_texte(prenom)[:20] or "ELEVE"
        nom_normalise = _normaliser_texte(nom)[:3] or "XXX"
        base = f"{prenom_normalise}-{nom_normalise}"
        for numero in range(100):
            code = f"{base}{numero:02d}"
            if not cls.objects.filter(code_etudiant=code).exists():
                return code
        for numero in range(10000):
            code = f"{base}{numero:04d}"
            if not cls.objects.filter(code_etudiant=code).exists():
                return code
        raise ValidationError(
            "Impossible de générer un identifiant unique pour "
            f"{prenom} {nom}."
        )

    def save(self, *args, **kwargs) -> None:
        if not self.code_etudiant:
            self.code_etudiant = type(self).generer_code_etudiant(
                self.nom, self.prenom
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.prenom} {self.nom} ({self.code_etudiant})"


class Session(models.Model):
    STATUT_ATTENTE = "attente"
    STATUT_EN_COURS = "en_cours"
    STATUT_PAUSE = "pause"
    STATUT_FINI = "fini"
    STATUTS = (
        (STATUT_ATTENTE, "En attente"),
        (STATUT_EN_COURS, "En cours"),
        (STATUT_PAUSE, "En pause"),
        (STATUT_FINI, "Terminée"),
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="QCM",
    )
    groupe = models.ForeignKey(
        Groupe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Groupe",
        help_text=(
            "Laisser vide pour une séance libre (démo) : les participants "
            "apparaîtront à la connexion."
        ),
    )
    code_session = models.CharField(
        "Code de session",
        max_length=8,
        unique=True,
        editable=False,
    )
    statut = models.CharField(
        "Statut",
        max_length=10,
        choices=STATUTS,
        default=STATUT_ATTENTE,
    )
    etape_courante = models.PositiveIntegerField("Étape courante", default=0)
    ends_at = models.DateTimeField("Fin de l'étape", null=True, blank=True)
    reste_en_pause = models.PositiveIntegerField(
        "Reste en pause (s)",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-id",)
        verbose_name = "Séance"
        verbose_name_plural = "Séances"

    def save(self, *args, **kwargs) -> None:
        if not self.code_session:
            self.code_session = self._generer_code_unique()
        super().save(*args, **kwargs)

    @classmethod
    def _generer_code_unique(cls) -> str:
        for _ in range(20):
            code = generer_code_session()
            if not cls.objects.filter(code_session=code).exists():
                return code
        raise RuntimeError("Impossible de générer un code de session unique.")

    def __str__(self) -> str:
        return f"{self.code_session} — {self.quiz.titre}"


class Participant(models.Model):
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Séance",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="participations",
        verbose_name="Élève",
    )
    jeton_appareil = models.UUIDField(
        "Jeton de l'appareil",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    derniere_activite = models.DateTimeField(
        "Dernière activité",
        null=True,
        blank=True,
    )
    couleur_assignee = models.PositiveSmallIntegerField(
        "Couleur assignée",
        validators=[MinValueValidator(1), MaxValueValidator(NB_COULEURS)],
        default=1,
    )
    graine_melange = models.PositiveBigIntegerField(
        "Graine de mélange",
        default=tirer_graine,
    )

    class Meta:
        ordering = ("id",)
        verbose_name = "Élève (Session)"
        verbose_name_plural = "Élèves (Session)"
        constraints = (
            models.UniqueConstraint(
                fields=["session", "student"],
                name="unique_participant_session_student",
                condition=models.Q(student__isnull=False),
            ),
        )

    @property
    def symbole(self) -> str:
        return COULEURS[self.couleur_assignee]["symbole"]

    def __str__(self) -> str:
        if self.student_id:
            return f"{self.student} — {self.symbole}"
        return f"Élève {self.pk} ({self.symbole})"


class Answer(models.Model):
    SOURCE_APP = "app"
    SOURCE_PAPIER = "papier"
    SOURCES = (
        (SOURCE_APP, "Application"),
        (SOURCE_PAPIER, "Papier"),
    )

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Séance",
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Élève",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="Question",
    )
    choix_selectionnes = models.JSONField("Choix sélectionnés", default=list)
    recu_a = models.DateTimeField("Reçu à", auto_now_add=True)
    source = models.CharField(
        "Source",
        max_length=10,
        choices=SOURCES,
        default=SOURCE_APP,
    )
    id_client = models.UUIDField("Identifiant client", unique=True)

    class Meta:
        verbose_name = "Réponse"
        verbose_name_plural = "Réponses"
        constraints = (
            models.UniqueConstraint(
                fields=["participant", "question"],
                name="unique_answer_participant_question",
            ),
        )
        indexes = (models.Index(fields=["session"], name="answer_session_idx"),)

    def save(self, *args, **kwargs) -> None:
        if self.participant_id and not self.session_id:
            self.session_id = self.participant.session_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.participant} → {self.question.uid}"

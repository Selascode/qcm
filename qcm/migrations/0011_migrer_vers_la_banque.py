# Schéma V3, étape 2/3 : migration des questions existantes vers la banque.
#
# Un ensemble « Questions existantes » est créé pour chaque professeur et
# toutes ses questions y sont rattachées. L'ancienne sélection de chaque QCM
# est reconstruite dans ``QuizQuestion`` en conservant l'ordre des étapes puis
# des questions. Les identifiants dupliqués entre plusieurs anciens QCM d'un
# même professeur sont suffixés avec l'identifiant du QCM : l'unicité V3 porte
# sur ``(set, uid)`` et non plus sur ``(quiz, uid)``.

from django.db import migrations

NOM_SET_PAR_DEFAUT = "Questions existantes"


def migrer_vers_la_banque(apps, schema_editor):
    Quiz = apps.get_model("qcm", "Quiz")
    Step = apps.get_model("qcm", "Step")
    Question = apps.get_model("qcm", "Question")
    QuestionSet = apps.get_model("qcm", "QuestionSet")
    QuizQuestion = apps.get_model("qcm", "QuizQuestion")

    proprietaires = (
        Question.objects.order_by()
        .values_list("quiz__proprietaire_id", flat=True)
        .distinct()
    )
    for proprietaire_id in list(proprietaires):
        question_set, _ = QuestionSet.objects.get_or_create(
            proprietaire_id=proprietaire_id,
            nom=NOM_SET_PAR_DEFAUT,
        )
        questions = list(
            Question.objects.filter(quiz__proprietaire_id=proprietaire_id)
            .select_related("quiz", "step")
            .order_by("quiz_id", "step__numero", "ordre", "id")
        )
        identifiants_existants = {question.uid for question in questions}
        identifiants_utilises: set[str] = set()
        for question in questions:
            uid = question.uid
            if uid in identifiants_utilises:
                base = f"{uid}-{question.quiz_id}"
                candidat = base
                numero = 2
                while (
                    candidat in identifiants_utilises
                    or candidat in identifiants_existants
                ):
                    candidat = f"{base}-{numero}"
                    numero += 1
                uid = candidat
            identifiants_utilises.add(uid)
            question.set_id = question_set.pk
            question.uid = uid
            if question.step_id:
                question.duree_s = question.step.duree_s
            question.save(update_fields=["set", "uid", "duree_s"])

    for quiz in Quiz.objects.all():
        premiere_etape = (
            Step.objects.filter(quiz=quiz).order_by("numero").first()
        )
        if premiere_etape is not None:
            quiz.duree_s = premiere_etape.duree_s
            quiz.save(update_fields=["duree_s"])
        questions = Question.objects.filter(quiz=quiz).order_by(
            "step__numero", "ordre", "id"
        )
        for position, question in enumerate(questions, start=1):
            QuizQuestion.objects.create(
                quiz=quiz,
                question=question,
                position=position,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("qcm", "0010_questionset_quizquestion_and_more"),
    ]

    operations = [
        migrations.RunPython(migrer_vers_la_banque, migrations.RunPython.noop),
    ]

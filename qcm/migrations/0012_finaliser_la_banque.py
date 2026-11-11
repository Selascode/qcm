# Schéma V3, étape 3/3 : suppression de l'ancien modèle et contraintes finales.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("qcm", "0011_migrer_vers_la_banque"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="step",
            name="unique_step_numero_par_quiz",
        ),
        migrations.RemoveConstraint(
            model_name="question",
            name="unique_question_uid_par_quiz",
        ),
        migrations.RemoveField(
            model_name="step",
            name="quiz",
        ),
        migrations.RemoveField(
            model_name="question",
            name="couleur_slot",
        ),
        migrations.RemoveField(
            model_name="question",
            name="quiz",
        ),
        migrations.RemoveField(
            model_name="question",
            name="step",
        ),
        migrations.AlterField(
            model_name="question",
            name="set",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="questions",
                to="qcm.questionset",
                verbose_name="Ensemble",
            ),
        ),
        migrations.DeleteModel(
            name="Step",
        ),
        migrations.AddConstraint(
            model_name="questionset",
            constraint=models.UniqueConstraint(
                fields=("proprietaire", "nom"),
                name="unique_question_set_nom_par_proprietaire",
            ),
        ),
        migrations.AddConstraint(
            model_name="quizquestion",
            constraint=models.UniqueConstraint(
                fields=("quiz", "question"),
                name="unique_question_par_quiz",
            ),
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                fields=("set", "uid"),
                name="unique_question_uid_par_set",
            ),
        ),
    ]

"""Rend le groupe obligatoire pour un élève (après vérification des données)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("qcm", "0004_verifier_student_groupe"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="groupe",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="etudiants",
                to="qcm.groupe",
                verbose_name="Groupe",
            ),
        ),
    ]

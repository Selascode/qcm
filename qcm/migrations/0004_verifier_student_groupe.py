"""Rend le rattachement d'un élève à un groupe explicite (V2).

La migration précédente a créé ``Student.groupe`` nullable pour permettre
l'ajout du modèle sans casser une base existante. Aucun élève n'existant avant
la V2, cette étape vérifie qu'aucune ligne orpheline ne subsiste avant de
rendre la colonne obligatoire.
"""

from django.db import migrations


def verifier_groupes(apps, schema_editor):
    Student = apps.get_model("qcm", "Student")
    if Student.objects.filter(groupe__isnull=True).exists():
        raise RuntimeError(
            "Des élèves sans groupe existent. Rattachez-les à un groupe avant "
            "de rendre Student.groupe obligatoire."
        )


class Migration(migrations.Migration):
    dependencies = [
        (
            "qcm",
            "0003_participant_derniere_activite_quiz_facteur_penalite_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(verifier_groupes, migrations.RunPython.noop),
    ]

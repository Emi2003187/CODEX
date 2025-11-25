from django.db import migrations, models


def copiar_codigo(apps, schema_editor):
    MedicamentoCatalogo = apps.get_model("consultorio_API", "MedicamentoCatalogo")
    for med in MedicamentoCatalogo.objects.all():
        med.clave = med.codigo_barras
        med.save(update_fields=["clave"])


class Migration(migrations.Migration):

    dependencies = [
        ("consultorio_API", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicamentocatalogo",
            name="clave",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(copiar_codigo, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="medicamentocatalogo",
            name="clave",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.RemoveField(
            model_name="medicamentocatalogo",
            name="codigo_barras",
        ),
    ]

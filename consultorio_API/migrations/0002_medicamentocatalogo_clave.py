from django.db import migrations, models


def add_clave_column(apps, schema_editor):
    MedicamentoCatalogo = apps.get_model("consultorio_API", "MedicamentoCatalogo")
    table_name = MedicamentoCatalogo._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if "clave" in existing_columns:
        return

    field = models.CharField(max_length=100, null=True, blank=True)
    field.set_attributes_from_name("clave")
    schema_editor.add_field(MedicamentoCatalogo, field)


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
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_clave_column, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="medicamentocatalogo",
                    name="clave",
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
            ],
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

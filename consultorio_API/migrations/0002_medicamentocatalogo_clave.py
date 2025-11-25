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
    table_name = MedicamentoCatalogo._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if "codigo_barras" not in existing_columns:
        return

    # Limit selected columns to avoid touching non-existent fields on databases
    # that already dropped codigo_barras.
    for med in MedicamentoCatalogo.objects.only("pk", "clave", "codigo_barras"):
        med.clave = med.codigo_barras
        med.save(update_fields=["clave"])


def normalizar_clave(apps, schema_editor):
    MedicamentoCatalogo = apps.get_model("consultorio_API", "MedicamentoCatalogo")
    table_name = MedicamentoCatalogo._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    has_codigo = "codigo_barras" in existing_columns
    used = set()

    queryset = MedicamentoCatalogo.objects.order_by("pk").only("pk", "clave")
    if has_codigo:
        queryset = queryset.only("pk", "clave", "codigo_barras")

    for med in queryset:
        raw_value = med.clave
        if not raw_value and has_codigo:
            raw_value = med.codigo_barras

        if not raw_value:
            raw_value = f"AUTO-{med.pk}"

        base = str(raw_value)[:100]
        candidate = base
        counter = 1
        while candidate in used:
            suffix = f"-{counter}"
            candidate = f"{base[: 100 - len(suffix)]}{suffix}"
            counter += 1

        if med.clave != candidate:
            med.clave = candidate
            med.save(update_fields=["clave"])

        used.add(candidate)


def drop_codigo_if_exists(apps, schema_editor):
    MedicamentoCatalogo = apps.get_model("consultorio_API", "MedicamentoCatalogo")
    table_name = MedicamentoCatalogo._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if "codigo_barras" not in existing_columns:
        return

    field = models.CharField(max_length=50, unique=True)
    field.set_attributes_from_name("codigo_barras")
    schema_editor.remove_field(MedicamentoCatalogo, field)


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
        migrations.RunPython(normalizar_clave, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="medicamentocatalogo",
            name="clave",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_codigo_if_exists, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="medicamentocatalogo",
                    name="codigo_barras",
                ),
            ],
        ),
    ]

from django.db import migrations, models


def forwards(apps, schema_editor):
    table = apps.get_model("consultorio_API", "MedicamentoCatalogo")._meta.db_table
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table)
        }

        if "clave" not in existing_columns:
            if "codigo_barras" in existing_columns:
                cursor.execute(
                    f"ALTER TABLE {table} CHANGE COLUMN codigo_barras clave varchar(100)"
                )
            else:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN clave varchar(100)"
                )

        cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN clave varchar(100)")

        constraints = connection.introspection.get_constraints(cursor, table)
        has_clave_unique = any(
            details.get("unique") and set(details.get("columns", [])) == {"clave"}
            for details in constraints.values()
        )

        if not has_clave_unique:
            cursor.execute(f"ALTER TABLE {table} ADD UNIQUE INDEX clave_unique (clave)")

        refreshed_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table)
        }

        if "codigo_barras" in refreshed_columns:
            cursor.execute(f"ALTER TABLE {table} DROP COLUMN codigo_barras")


class Migration(migrations.Migration):
    dependencies = [
        ("consultorio_API", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop)
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="medicamentocatalogo",
                    old_name="codigo_barras",
                    new_name="clave",
                ),
                migrations.AlterField(
                    model_name="medicamentocatalogo",
                    name="clave",
                    field=models.CharField(max_length=100, unique=True),
                ),
            ],
        ),
    ]

from django.db import migrations


def add_registrado_por(apps, schema_editor):
    # Check if the column already exists to avoid duplicate column errors
    table = 'consultorio_API_signosvitales'
    column = 'registrado_por_id'
    with schema_editor.connection.cursor() as cursor:
        existing_columns = [c.name for c in schema_editor.connection.introspection.get_table_description(cursor, table)]
        if column not in existing_columns:
            SignosVitales = apps.get_model('consultorio_API', 'SignosVitales')
            field = SignosVitales._meta.get_field('registrado_por')
            schema_editor.add_field(SignosVitales, field)


class Migration(migrations.Migration):

    dependencies = [
        ("consultorio_API", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_registrado_por, migrations.RunPython.noop),
    ]

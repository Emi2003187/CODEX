from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('consultorio_API', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS existencia integer UNSIGNED NOT NULL DEFAULT 0",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN existencia",
                ),
            ],
        ),
    ]

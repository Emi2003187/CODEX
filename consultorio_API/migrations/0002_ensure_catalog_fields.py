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
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS nombre varchar(255) NOT NULL",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS nombre",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS codigo_barras varchar(50) NOT NULL UNIQUE",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS codigo_barras",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS existencia integer UNSIGNED NOT NULL DEFAULT 0",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS existencia",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS departamento varchar(100) NULL",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS departamento",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS precio decimal(10,2) NULL",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS precio",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS categoria varchar(100) NULL",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS categoria",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE consultorio_API_medicamentocatalogo ADD COLUMN IF NOT EXISTS imagen varchar(100) NULL",
                    reverse_sql="ALTER TABLE consultorio_API_medicamentocatalogo DROP COLUMN IF EXISTS imagen",
                ),
            ],
        ),
    ]

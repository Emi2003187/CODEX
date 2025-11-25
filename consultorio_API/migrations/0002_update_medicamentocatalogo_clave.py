from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("consultorio_API", "0001_initial"),
    ]

    operations = [
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
    ]

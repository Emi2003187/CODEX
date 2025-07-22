from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RemoveField(
            model_name='paciente',
            name='consultorio_asignado',
        ),
        migrations.AddField(
            model_name='paciente',
            name='consultorio',
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pacientes',
                to='consultorio_API.consultorio',
            ),
            preserve_default=False,
        ),
    ]

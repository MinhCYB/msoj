from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('judge', '0236_judge_storages')]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='judge_generation',
            field=models.PositiveIntegerField(default=0, verbose_name='judging generation'),
        ),
    ]

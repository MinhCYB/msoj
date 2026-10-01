from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('mentor', '0002_review_history')]

    operations = [
        migrations.AddField(
            model_name='aireviewattempt',
            name='provider_call_started_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]

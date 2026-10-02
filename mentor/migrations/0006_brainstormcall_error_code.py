from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('mentor', '0005_brainstormsession_mentor_brainstorm_scope_kind_valid')]

    operations = [
        migrations.AddField(
            model_name='brainstormcall',
            name='error_code',
            field=models.CharField(blank=True, max_length=40),
        ),
    ]

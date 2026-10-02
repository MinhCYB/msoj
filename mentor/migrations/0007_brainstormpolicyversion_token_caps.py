from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('mentor', '0006_brainstormcall_error_code')]

    operations = [
        migrations.AddField(
            model_name='brainstormpolicyversion', name='generator_max_tokens',
            field=models.PositiveIntegerField(default=1200),
        ),
        migrations.AddField(
            model_name='brainstormpolicyversion', name='reviewer_max_tokens',
            field=models.PositiveIntegerField(default=256),
        ),
    ]

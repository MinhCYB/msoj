from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mentor', '0013_authoring_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='brainstormmessage',
            name='approved_visuals',
            field=models.JSONField(blank=True, default=list),
        ),
    ]

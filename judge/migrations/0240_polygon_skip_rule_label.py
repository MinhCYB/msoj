from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('judge', '0239_polygon_tags_error'),
    ]

    operations = [
        migrations.AlterField(
            model_name='polygonproblem',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'Not synced'),
                    ('synced', 'Synced'),
                    ('outdated', 'Newer revision available'),
                    ('skipped', 'Skipped by sync rule'),
                    ('duplicate', 'Duplicate code'),
                    ('conflict', 'Code taken by another problem'),
                    ('failed', 'Failed'),
                ],
                db_index=True,
                default='new',
                max_length=16,
                verbose_name='status',
            ),
        ),
    ]

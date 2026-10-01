from django.db import migrations, models
import django.db.models.deletion


STATUS_CHOICES = [
    ('pending', 'Pending'), ('running', 'Running'), ('succeeded', 'Succeeded'),
    ('failed', 'Failed'), ('stale', 'Stale'),
]


def migrate_legacy_reviews(apps, schema_editor):
    Review = apps.get_model('mentor', 'AIReview')
    Attempt = apps.get_model('mentor', 'AIReviewAttempt')
    Approach = apps.get_model('mentor', 'AIReviewApproach')
    for review in Review.objects.using(schema_editor.connection.alias).all().iterator():
        # Legacy output has no provable judge/source revision: preserve it for admin audit only.
        attempt = Attempt.objects.using(schema_editor.connection.alias).create(
            review_id=review.pk, generation=0, review_revision='', status='stale',
            overall_feedback=review.overall_feedback,
        )
        Approach.objects.using(schema_editor.connection.alias).filter(review_id=review.pk).update(attempt_id=attempt.pk)


def restore_legacy_reviews(apps, schema_editor):
    Attempt = apps.get_model('mentor', 'AIReviewAttempt')
    Approach = apps.get_model('mentor', 'AIReviewApproach')
    for attempt in Attempt.objects.using(schema_editor.connection.alias).filter(generation=0).iterator():
        Approach.objects.using(schema_editor.connection.alias).filter(attempt_id=attempt.pk).update(review_id=attempt.review_id)


def mark_legacy_stale(apps, schema_editor):
    apps.get_model('mentor', 'AIReview').objects.using(schema_editor.connection.alias).filter(
        current_revision='').update(status='stale', overall_feedback='')


class Migration(migrations.Migration):
    dependencies = [
        ('judge', '0237_submission_judge_generation'),
        ('mentor', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='aireview', name='status', field=models.CharField(
            max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)),
        migrations.AddField(model_name='aireview', name='current_revision', field=models.CharField(max_length=80, blank=True)),
        migrations.AddField(model_name='aireview', name='current_generation', field=models.PositiveIntegerField(default=0)),
        migrations.AlterField(model_name='aireview', name='overall_feedback', field=models.TextField(blank=True)),
        migrations.AddField(model_name='aireview', name='requested_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='aireview', name='started_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='aireview', name='completed_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name='aireview', name='error_code', field=models.CharField(max_length=40, blank=True)),
        migrations.CreateModel(name='AIReviewAttempt', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('generation', models.PositiveIntegerField()),
            ('review_revision', models.CharField(max_length=80, blank=True)),
            ('status', models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')),
            ('provider', models.CharField(max_length=100, blank=True)),
            ('requested_model', models.CharField(max_length=200, blank=True)),
            ('returned_model', models.CharField(max_length=200, blank=True)),
            ('input_tokens', models.PositiveIntegerField(null=True, blank=True)),
            ('output_tokens', models.PositiveIntegerField(null=True, blank=True)),
            ('total_tokens', models.PositiveIntegerField(null=True, blank=True)),
            ('finish_reason', models.CharField(max_length=40, blank=True)),
            ('error_code', models.CharField(max_length=40, blank=True)),
            ('overall_feedback', models.TextField(blank=True)),
            ('requested_at', models.DateTimeField(null=True, blank=True)),
            ('started_at', models.DateTimeField(null=True, blank=True)),
            ('completed_at', models.DateTimeField(null=True, blank=True)),
            ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                         related_name='attempts', to='mentor.aireview')),
        ], options={
            'indexes': [models.Index(fields=['status', 'requested_at'], name='mentor_attempt_status_idx')],
            'constraints': [models.UniqueConstraint(fields=['review', 'generation'],
                                                    name='mentor_review_attempt_generation_uniq')],
        }),
        migrations.AddField(model_name='aireviewapproach', name='attempt', field=models.ForeignKey(
            to='mentor.aireviewattempt', related_name='approaches', null=True, blank=True,
            on_delete=django.db.models.deletion.CASCADE)),
        migrations.RunPython(migrate_legacy_reviews, restore_legacy_reviews),
        migrations.RemoveField(model_name='aireviewapproach', name='review'),
        migrations.AlterField(model_name='aireviewapproach', name='attempt', field=models.ForeignKey(
            to='mentor.aireviewattempt', related_name='approaches', on_delete=django.db.models.deletion.CASCADE)),
        migrations.RunPython(mark_legacy_stale, migrations.RunPython.noop),
    ]

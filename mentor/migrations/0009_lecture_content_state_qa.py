from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mentor', '0008_roadmap_foundation'),
    ]

    operations = [
        migrations.AddField(
            model_name='topiclesson',
            name='summary',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.CreateModel(
            name='TopicLessonState',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_revision', models.PositiveIntegerField()),
                ('offset', models.PositiveIntegerField(default=0)),
                ('position_version', models.PositiveBigIntegerField(default=0)),
                ('last_accessed_at', models.DateTimeField(auto_now=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learner_states', to='mentor.topiclesson')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_lesson_states', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-last_accessed_at', 'pk'),
            },
        ),
        migrations.AddConstraint(
            model_name='topiclessonstate',
            constraint=models.UniqueConstraint(fields=('user', 'lesson'), name='mentor_lesson_user_state'),
        ),
        migrations.AddConstraint(
            model_name='topiclessonstate',
            constraint=models.CheckConstraint(check=models.Q(offset__gte=0, offset__lte=10000), name='mentor_lesson_state_offset_range'),
        ),
        migrations.CreateModel(
            name='TopicLessonQAMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_revision', models.PositiveIntegerField()),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=10)),
                ('content', models.TextField()),
                ('section', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qa_messages', to='mentor.topiclesson')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_lesson_qa_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('created_at', 'pk'),
            },
        ),
        migrations.AddIndex(
            model_name='topiclessonqamessage',
            index=models.Index(fields=['user', 'lesson', 'content_revision'], name='mentor_qa_user_lesson_rev_idx'),
        ),
        migrations.AddConstraint(
            model_name='topiclessonqamessage',
            constraint=models.CheckConstraint(check=models.Q(role__in=('user', 'assistant')), name='mentor_lesson_qa_role_valid'),
        ),
        migrations.CreateModel(
            name='TopicLessonQAAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_revision', models.PositiveIntegerField()),
                ('claim_token', models.CharField(db_index=True, max_length=64)),
                ('status', models.CharField(choices=[('active', 'Active'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('rejected', 'Rejected')], default='active', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qa_attempts', to='mentor.topiclesson')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_lesson_qa_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', 'pk'),
            },
        ),
        migrations.AddIndex(
            model_name='topiclessonqaattempt',
            index=models.Index(fields=['user', 'status'], name='mentor_qa_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='topiclessonqaattempt',
            index=models.Index(fields=['user', 'lesson', 'content_revision'], name='mentor_qa_att_user_rev_idx'),
        ),
        migrations.AddIndex(
            model_name='topiclessonqaattempt',
            index=models.Index(fields=['user', 'created_at'], name='mentor_qa_att_user_time_idx'),
        ),
        migrations.AddConstraint(
            model_name='topiclessonqaattempt',
            constraint=models.CheckConstraint(check=models.Q(status__in=('active', 'succeeded', 'failed', 'rejected')), name='mentor_lesson_qa_status_valid'),
        ),
    ]

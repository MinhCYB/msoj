from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion
import mptt.fields


def preserve_legacy(apps, schema_editor):
    """Quarantine legacy placements as draft roots; prerequisites are not parents."""
    alias = schema_editor.connection.alias
    Roadmap = apps.get_model('mentor', 'Roadmap')
    Node = apps.get_model('mentor', 'RoadmapNode')
    Link = apps.get_model('mentor', 'NodeProblem')
    scopes = {}
    tree_id = 0
    for node in Node.objects.using(alias).order_by('pk').iterator():
        scope = node.organization_id
        if scope not in scopes:
            slug = f'legacy-organization-{scope}' if scope else 'legacy-public'
            roadmap = Roadmap.objects.using(alias).create(
                title=f'Legacy roadmap — organization {scope}' if scope else 'Legacy roadmap',
                slug=slug, visibility='ORGANIZATION' if scope else 'PUBLIC',
                organization_id=scope, status='DRAFT')
            scopes[scope] = roadmap.pk
        tree_id += 1
        Node.objects.using(alias).filter(pk=node.pk).update(
            roadmap_id=scopes[scope], slug=f'legacy-node-{node.pk}',
            parent_id=None, lft=1, rght=2, tree_id=tree_id, level=0, status='DRAFT')
        if node.problem_id:
            Link.objects.using(alias).create(node_id=node.pk, problem_id=node.problem_id, position=0)
    # Topic IDs, introductions, optional flags and prerequisite rows remain intact.
    # A topic shared across scopes remains draft/public at schema level, not readable.


def preserve_topic_permissions(apps, schema_editor):
    alias = schema_editor.connection.alias
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    for content_type in ContentType.objects.using(alias).filter(app_label='mentor', model__in=('topic', 'learningtopic')):
        for action in ('add', 'change', 'delete', 'view'):
            Permission.objects.using(alias).filter(content_type=content_type, codename=f'{action}_topic').update(
                codename=f'{action}_learningtopic', name=f'Can {action} learning topic')


class Migration(migrations.Migration):
    dependencies = [('mentor', '0007_brainstormpolicyversion_token_caps')]

    operations = [
        migrations.RenameModel('Topic', 'LearningTopic'),
        migrations.RunPython(preserve_topic_permissions, migrations.RunPython.noop),
        migrations.RenameField('LearningTopic', 'description', 'introduction'),
        migrations.RenameField('RoadmapNode', 'topic', 'learning_topic'),
        migrations.RenameField('RoadmapNode', 'order', 'position'),
        migrations.CreateModel(name='Roadmap', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('title', models.CharField(max_length=200)),
            ('slug', models.SlugField(max_length=100, unique=True)),
            ('introduction', models.TextField(blank=True)),
            ('status', models.CharField(max_length=10, choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published')], default='DRAFT')),
            ('visibility', models.CharField(max_length=12, choices=[('PUBLIC', 'Public'), ('ORGANIZATION', 'Organization')], default='PUBLIC')),
            ('tree_revision', models.PositiveIntegerField(default=1, editable=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.ForeignKey('judge.organization', blank=True, null=True, on_delete=django.db.models.deletion.PROTECT)),
        ], options={'ordering': ('pk',), 'permissions': [('publish_roadmap', 'Publish learning content and roadmaps')]}),
        migrations.AddField('LearningTopic', 'status', models.CharField(max_length=10, choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published')], default='DRAFT')),
        migrations.AddField('LearningTopic', 'visibility', models.CharField(max_length=12, choices=[('PUBLIC', 'Public'), ('ORGANIZATION', 'Organization')], default='PUBLIC')),
        migrations.AddField('LearningTopic', 'organization', models.ForeignKey('judge.organization', blank=True, null=True, on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField('LearningTopic', 'content_revision', models.PositiveIntegerField(default=1, editable=False)),
        migrations.AddField('LearningTopic', 'created_at', models.DateTimeField(auto_now_add=True, default=timezone.now), preserve_default=False),
        migrations.AddField('LearningTopic', 'updated_at', models.DateTimeField(auto_now=True)),
        migrations.AlterModelOptions('LearningTopic', {'ordering': ('name', 'pk')}),
        migrations.AddField('RoadmapNode', 'roadmap', models.ForeignKey('mentor.roadmap', related_name='nodes', on_delete=django.db.models.deletion.PROTECT, null=True)),
        migrations.AddField('RoadmapNode', 'parent', mptt.fields.TreeForeignKey('mentor.roadmapnode', null=True, blank=True, related_name='children', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField('RoadmapNode', 'slug', models.SlugField(max_length=100, default=''), preserve_default=False),
        migrations.AddField('RoadmapNode', 'type', models.CharField(max_length=5, choices=[('GROUP', 'Group'), ('TOPIC', 'Topic')], default='TOPIC')),
        migrations.AddField('RoadmapNode', 'difficulty', models.CharField(max_length=12, choices=[('BASIC', 'Basic'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')], null=True, blank=True)),
        migrations.AddField('RoadmapNode', 'status', models.CharField(max_length=10, choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published')], default='DRAFT')),
        migrations.AddField('RoadmapNode', 'lft', models.PositiveIntegerField(default=0, editable=False), preserve_default=False),
        migrations.AddField('RoadmapNode', 'rght', models.PositiveIntegerField(default=0, editable=False), preserve_default=False),
        migrations.AddField('RoadmapNode', 'tree_id', models.PositiveIntegerField(default=0, db_index=True, editable=False), preserve_default=False),
        migrations.AddField('RoadmapNode', 'level', models.PositiveIntegerField(default=0, editable=False), preserve_default=False),
        migrations.AlterField('RoadmapNode', 'learning_topic', models.ForeignKey('mentor.learningtopic', null=True, blank=True, related_name='roadmap_nodes', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AlterField('RoadmapNode', 'is_optional_review', models.BooleanField(default=False, help_text='Optional review node; does not enforce prerequisite gating.')),
        migrations.AlterModelOptions('RoadmapNode', {}),
        migrations.CreateModel(name='TopicLesson', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('title', models.CharField(max_length=200)),
            ('slug', models.SlugField(max_length=100)),
            ('position', models.PositiveIntegerField(default=0)),
            ('body', models.TextField(blank=True)),
            ('status', models.CharField(max_length=10, choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published')], default='DRAFT')),
            ('content_revision', models.PositiveIntegerField(default=1, editable=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('topic', models.ForeignKey('mentor.learningtopic', related_name='lessons', on_delete=django.db.models.deletion.PROTECT)),
        ], options={'ordering': ('position', 'pk')}),
        migrations.CreateModel(name='NodeProblem', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('position', models.PositiveIntegerField(default=0)),
            ('node', models.ForeignKey('mentor.roadmapnode', related_name='problem_links', on_delete=django.db.models.deletion.CASCADE)),
            ('problem', models.ForeignKey('judge.problem', related_name='mentor_roadmap_links', on_delete=django.db.models.deletion.PROTECT)),
        ], options={'ordering': ('position', 'pk')}),
        migrations.RunPython(preserve_legacy),
        migrations.AlterField('RoadmapNode', 'roadmap', models.ForeignKey('mentor.roadmap', related_name='nodes', on_delete=django.db.models.deletion.PROTECT)),
        migrations.RemoveField('RoadmapNode', 'problem'),
        migrations.RemoveField('RoadmapNode', 'organization'),
        migrations.AlterField('RoadmapPrerequisite', 'node', models.ForeignKey('mentor.roadmapnode', related_name='prerequisites', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AlterField('RoadmapPrerequisite', 'prerequisite', models.ForeignKey('mentor.roadmapnode', related_name='required_by', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddConstraint('Roadmap', models.CheckConstraint(check=models.Q(status__in=['DRAFT', 'PUBLISHED']), name='mentor_roadmap_status')),
        migrations.AddConstraint('Roadmap', models.CheckConstraint(check=(models.Q(visibility='PUBLIC', organization__isnull=True) | models.Q(visibility='ORGANIZATION', organization__isnull=False)), name='mentor_roadmap_scope')),
        migrations.AddConstraint('LearningTopic', models.CheckConstraint(check=models.Q(status__in=['DRAFT', 'PUBLISHED']), name='mentor_topic_status')),
        migrations.AddConstraint('LearningTopic', models.CheckConstraint(check=(models.Q(visibility='PUBLIC', organization__isnull=True) | models.Q(visibility='ORGANIZATION', organization__isnull=False)), name='mentor_topic_scope')),
        migrations.AddConstraint('TopicLesson', models.UniqueConstraint(fields=('topic', 'slug'), name='mentor_lesson_slug')),
        migrations.AddConstraint('TopicLesson', models.CheckConstraint(check=models.Q(status__in=['DRAFT', 'PUBLISHED']), name='mentor_lesson_status')),
        migrations.AddConstraint('RoadmapNode', models.UniqueConstraint(fields=('roadmap', 'slug'), name='mentor_node_slug')),
        migrations.AddConstraint('RoadmapNode', models.CheckConstraint(check=models.Q(type__in=('GROUP', 'TOPIC')), name='mentor_node_type')),
        migrations.AddConstraint('RoadmapNode', models.CheckConstraint(check=models.Q(status__in=['DRAFT', 'PUBLISHED']), name='mentor_node_status')),
        migrations.AddConstraint('RoadmapNode', models.CheckConstraint(check=(models.Q(difficulty__isnull=True) | models.Q(difficulty__in=('BASIC', 'INTERMEDIATE', 'ADVANCED'))), name='mentor_node_difficulty')),
        migrations.AddConstraint('NodeProblem', models.UniqueConstraint(fields=('node', 'problem'), name='mentor_node_problem')),
        migrations.AlterIndexTogether('RoadmapNode', {('tree_id', 'lft')}),
    ]

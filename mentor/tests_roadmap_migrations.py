"""Forward migration rehearsals on a separate disposable database, never deployment."""
from copy import deepcopy
from uuid import uuid4

from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings


class RehearsalRouter:
    def __init__(self, target_alias='roadmap_migration'):
        self.target_alias = target_alias

    def db_for_read(self, model, **hints):
        return self.target_alias

    def db_for_write(self, model, **hints):
        return self.target_alias

class RoadmapMigrationTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        super().setUp()
        default = connections['default']
        if default.vendor != 'mysql':
            self.skipTest('Migration rehearsal uses the deployment-compatible MySQL backend.')
        self.database_name = 'test_roadmap_migration_' + uuid4().hex[:12]
        self.alias = 'roadmap_migration'
        config = deepcopy(default.settings_dict)
        config['NAME'] = self.database_name
        config['TEST']['MIRROR'] = None
        with default.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{self.database_name}` CHARACTER SET utf8mb4')
        connections.databases[self.alias] = config
        self.db = connections[self.alias]
        self.addCleanup(self.cleanup_database)
        executor = MigrationExecutor(self.db)
        # Historical Judge data migrations omit .using(schema_editor.connection.alias).
        # Keep those reads isolated without modifying existing migrations.
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter()]):
            executor.migrate([('mentor', '0007_brainstormpolicyversion_token_caps')])
        self.old_apps = executor.loader.project_state([('mentor', '0007_brainstormpolicyversion_token_caps')]).apps

    def cleanup_database(self):
        self.db.close()
        del connections[self.alias]
        del connections.databases[self.alias]
        with connections['default'].cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{self.database_name}`')

    def migrate_forward(self):
        executor = MigrationExecutor(self.db)
        target = [('mentor', '0008_roadmap_foundation')]
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter()]):
            executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_empty_database_does_not_seed_or_publish(self):
        apps = self.migrate_forward()
        self.assertEqual(apps.get_model('mentor', 'Roadmap').objects.using(self.alias).count(), 0)
        self.assertEqual(apps.get_model('mentor', 'RoadmapNode').objects.using(self.alias).count(), 0)

    def test_populated_legacy_keeps_ids_scopes_edges_optional_links_and_permissions(self):
        def model(app, name):
            return self.old_apps.get_model(app, name).objects.using(self.alias)

        topic = model('mentor', 'Topic').create(name='Legacy shared', slug='legacy', description='Old theory')
        org = model('judge', 'Organization').create(slug='legacy_org', name='Legacy organization',
                                                    short_name='Legacy', about='', slots=10)
        group = model('judge', 'ProblemGroup').create(name='legacy', full_name='Legacy')
        problem = model('judge', 'Problem').create(code='legacy_problem', name='Legacy problem',
                                                   group_id=group.pk, time_limit=1, memory_limit=65536, points=100)
        a = model('mentor', 'RoadmapNode').create(topic_id=topic.pk, problem_id=problem.pk, title='A',
                                                  order=9, is_optional_review=True, organization_id=org.pk)
        b = model('mentor', 'RoadmapNode').create(topic_id=topic.pk, title='B', order=2)
        edge = model('mentor', 'RoadmapPrerequisite').create(node_id=b.pk, prerequisite_id=a.pk)
        ct = model('contenttypes', 'ContentType').create(app_label='mentor', model='topic')
        permission = model('auth', 'Permission').create(content_type_id=ct.pk, codename='change_topic', name='Old')
        role = model('auth', 'Group').create(name='Legacy editor')
        role.permissions.add(permission)
        apps = self.migrate_forward()
        Topic = apps.get_model('mentor', 'LearningTopic')
        Node = apps.get_model('mentor', 'RoadmapNode')
        Link = apps.get_model('mentor', 'NodeProblem')
        migrated_topic = Topic.objects.using(self.alias).get(pk=topic.pk)
        self.assertEqual((migrated_topic.introduction, migrated_topic.status), ('Old theory', 'DRAFT'))
        migrated_a = Node.objects.using(self.alias).select_related('roadmap').get(pk=a.pk)
        migrated_b = Node.objects.using(self.alias).select_related('roadmap').get(pk=b.pk)
        self.assertEqual((migrated_a.position, migrated_a.is_optional_review, migrated_a.parent_id), (9, True, None))
        self.assertEqual(migrated_a.roadmap.organization_id, org.pk)
        self.assertEqual(migrated_a.roadmap.visibility, 'ORGANIZATION')
        self.assertEqual(migrated_b.roadmap.visibility, 'PUBLIC')
        self.assertNotEqual(migrated_a.roadmap_id, migrated_b.roadmap_id)
        self.assertEqual((migrated_a.learning_topic_id, migrated_b.learning_topic_id), (topic.pk, topic.pk))
        self.assertEqual(Link.objects.using(self.alias).get(node_id=a.pk).problem_id, problem.pk)
        migrated_edge = apps.get_model('mentor', 'RoadmapPrerequisite').objects.using(self.alias).get(pk=edge.pk)
        self.assertEqual((migrated_edge.node_id, migrated_edge.prerequisite_id), (b.pk, a.pk))
        self.assertEqual(list(Node.objects.using(self.alias).values_list('status', flat=True)), ['DRAFT', 'DRAFT'])
        for node in (migrated_a, migrated_b):
            self.assertEqual((node.lft, node.rght, node.level), (1, 2, 0))
        self.assertEqual(apps.get_model('auth', 'Permission').objects.using(self.alias).get(pk=permission.pk).codename,
                         'change_learningtopic')
        self.assertEqual(apps.get_model('auth', 'Group').objects.using(self.alias).get(pk=role.pk)
                         .permissions.get(pk=permission.pk).pk, permission.pk)

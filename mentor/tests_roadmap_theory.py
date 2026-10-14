"""Behavioral protection for development content import and author edits."""
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from judge.models import Profile
from mentor.roadmap_models import LearningTopic, Roadmap, RoadmapNode, TopicLesson


@override_settings(DEBUG=True)
class TheorySeedTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('theory-editor', '', 'test-password')
        Profile.objects.create(user=self.staff)
        self.roadmap = Roadmap.objects.create(title='CP', slug='competitive-programming', status='PUBLISHED')
        self.group = RoadmapNode.objects.create(roadmap=self.roadmap, title='Group', slug='group', type='GROUP', status='PUBLISHED')
        self.entries = []
        self.notes = []
        for position, slug in enumerate(('first', 'second')):
            RoadmapNode.objects.create(roadmap=self.roadmap, parent=self.group, title=slug,
                                       slug=slug, position=position, status='PUBLISHED')
            self.entries.append({'slug': slug, 'title': slug, 'parent': 'group', 'type': 'TOPIC',
                                 'difficulty': None, 'position': position})
            self.notes.append({'node_slug': slug, 'title': slug, 'body': '# Model\n\nAn original explanation.',
                               'summary': 'A concrete summary.', 'introduction': 'An introduction.'})
        self.entries.append({'slug': 'group', 'title': 'Group', 'parent': None, 'type': 'GROUP', 'difficulty': None, 'position': 0})
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'notes.json'
        path.write_text(json.dumps(self.notes), encoding='utf-8')
        self.manifest = patch('mentor.management.commands.seed_roadmap_theory.load_curriculum_manifest',
                              return_value={'roadmap': {'slug': self.roadmap.slug}, 'nodes': self.entries})
        self.path_patch = patch('mentor.management.commands.seed_roadmap_theory.NOTES_PATH', path)
        self.manifest.start()
        self.path_patch.start()
        self.addCleanup(self.manifest.stop)
        self.addCleanup(self.path_patch.stop)

    def seed(self, **options):
        call_command('seed_roadmap_theory', stdout=io.StringIO(), **options)

    def test_dry_run_no_writes_and_apply_no_duplicates_or_revision_churn(self):
        self.seed()
        self.assertFalse(LearningTopic.objects.exists())
        nodes = list(RoadmapNode.objects.values_list('pk', 'parent_id', 'lft', 'rght', 'position'))
        self.seed(apply=True, development=True, user=self.staff.username)
        before = list(TopicLesson.objects.values_list('pk', 'content_revision'))
        self.assertEqual(list(RoadmapNode.objects.values_list('pk', 'parent_id', 'lft', 'rght', 'position')), nodes)
        self.seed(apply=True, development=True, user=self.staff.username)
        self.assertEqual(list(TopicLesson.objects.values_list('pk', 'content_revision')), before)
        self.assertEqual(list(RoadmapNode.objects.values_list('pk', 'parent_id', 'lft', 'rght', 'position')), nodes)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.learning_topic_id)
        self.assertEqual(TopicLesson.objects.count(), 2)

    def test_last_node_conflict_prevents_all_partial_content_writes(self):
        other = LearningTopic.objects.create(name='Owner content', slug='owner')
        second = RoadmapNode.objects.get(slug='second')
        second.learning_topic = other
        second.save()
        with self.assertRaises(CommandError):
            self.seed(apply=True, development=True, user=self.staff.username)
        self.assertEqual(list(LearningTopic.objects.values_list('slug', flat=True)), ['owner'])
        self.assertFalse(TopicLesson.objects.exists())

    def test_author_edits_are_never_overwritten(self):
        self.seed(apply=True, development=True, user=self.staff.username)
        lesson = TopicLesson.objects.get(topic__slug='cp-first')
        lesson.body = 'Owner revision with new teaching content.'
        lesson.save()
        with self.assertRaises(CommandError):
            self.seed(apply=True, development=True, user=self.staff.username)
        lesson.refresh_from_db()
        self.assertEqual(lesson.body, 'Owner revision with new teaching content.')

    def test_non_debug_and_missing_optin_or_permission_refuse_writes(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.seed(apply=True, development=True, user=self.staff.username)
        with self.assertRaises(CommandError):
            self.seed(apply=True, user=self.staff.username)
        viewer = User.objects.create_user('theory-viewer', is_staff=True)
        with self.assertRaises(CommandError):
            self.seed(apply=True, development=True, user=viewer.username)
        self.assertFalse(LearningTopic.objects.exists())

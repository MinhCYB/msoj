"""Consumer-visible guarantees of the one-way local Foundations cutover."""
import io
from copy import deepcopy

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from judge.models import PolygonProblem, PolygonTagMapping, ProblemType, Submission
from mentor.roadmap_curriculum import load_curriculum_manifest
from mentor.roadmap_models import (
    LearningTopic, NodeProblem, RoadmapNode, TopicLesson, TopicLessonQAMessage, TopicLessonState,
)
from mentor.roadmap_selectors import get_node_lesson_data, get_progress_data
from mentor.tests_roadmap import RoadmapFixture


@override_settings(DEBUG=True)
class FoundationsCutoverTests(RoadmapFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.roadmap.slug = 'competitive-programming'
        self.roadmap.save()
        manifest = deepcopy(load_curriculum_manifest())
        rename = {'loops': 'programming-basics', 'io-basics': 'io-and-numeric-safety',
                  'array-basics': 'arrays-and-strings', 'conditions': 'casework'}
        old = []
        for spec in manifest['nodes']:
            if spec['slug'] in {'functions', 'string-basics', 'matrix-basics'}:
                continue
            spec['slug'] = rename.get(spec['slug'], spec['slug'])
            spec['parent'] = rename.get(spec['parent'], spec['parent'])
            if spec['slug'] == 'queries':
                spec['parent'] = 'foundations'
            if spec['slug'] == 'complexity':
                spec['title'] = 'Độ phức tạp thuật toán (Complexity)'
                spec['position'] = 4
            old.append(spec)
        old.extend({'slug': slug, 'parent': 'foundations', 'type': 'TOPIC', 'title': slug,
                    'position': position, 'difficulty': 'BASIC'}
                   for position, slug in enumerate(('correctness', 'hardcode'), 20))
        nodes = {}
        while old:
            ready = [s for s in old if s['parent'] is None or s['parent'] in nodes]
            for spec in ready:
                node = RoadmapNode.objects.create(roadmap=self.roadmap, slug=spec['slug'],
                    title=spec['title'], parent=nodes.get(spec['parent']), type=spec['type'],
                    position=spec['position'], difficulty=spec.get('difficulty'), status='PUBLISHED')
                nodes[node.slug] = node
                old.remove(spec)
        self.nodes = nodes
        for slug in ('programming-basics', 'io-and-numeric-safety', 'arrays-and-strings',
                     'algorithmic-thinking', 'complexity', 'correctness', 'casework',
                     'implementation', 'hardcode', 'queries', 'brute-force'):
            topic = LearningTopic.objects.create(name=slug, slug='cp-' + slug, introduction='Original', status='PUBLISHED')
            node = nodes[slug]
            node.learning_topic = topic
            node.save()
            TopicLesson.objects.create(topic=topic, title=slug, slug='overview', body='Original ' + slug, status='PUBLISHED')
        self.lesson = self.nodes['programming-basics'].learning_topic.lessons.get()
        TopicLessonState.objects.create(user=self.learner, lesson=self.lesson, content_revision=1, offset=6200)
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=self.lesson, content_revision=1,
                                          role='assistant', content='Visible answer')
        self.problem_a = self.problem('msb_arraysum')
        self.problem_b = self.problem('msb_palinstr')
        self.link(self.nodes['arrays-and-strings'], self.problem_a)
        self.link(self.nodes['arrays-and-strings'], self.problem_b)
        self.submission(self.problem_a)
        self.old_type = ProblemType.objects.create(name='programming-basics', full_name='Old broad type')
        self.problem_a.types.add(self.old_type)
        self.legacy_string = self.problem('legacy_string')
        old_arrays = ProblemType.objects.create(name='arrays-and-strings', full_name='Old array/string umbrella')
        self.legacy_string.types.add(old_arrays)
        PolygonProblem.objects.create(polygon_id=5001, owner='ms24', name='legacy-string',
                                      problem=self.legacy_string, tags=['string'])
        self.link(self.nodes['arrays-and-strings'], self.legacy_string)
        self.custom_type = ProblemType.objects.create(name='owner-functions', full_name='Owner classification')
        PolygonTagMapping.objects.create(tag='functions', problem_type=self.custom_type)

    def cutover(self, **kwargs):
        call_command('restructure_foundations', stdout=io.StringIO(), **kwargs)

    def test_cutover_keeps_learning_state_and_ac_while_redistributing_exercises(self):
        before_submissions = list(Submission.objects.values())
        old_loop_id = self.nodes['programming-basics'].pk
        self.cutover(apply=True, development=True, user=self.staff.username)
        self.lesson.refresh_from_db()
        self.assertEqual((self.lesson.slug, self.lesson.body, self.lesson.content_revision),
                         ('programming-foundations-reference', 'Original programming-basics', 1))
        implementation = RoadmapNode.objects.get(roadmap=self.roadmap, slug='implementation')
        data = get_node_lesson_data(self.roadmap, implementation.pk, self.lesson.pk, self.learner)
        self.assertEqual(data['lecture_state']['resume_offset'], 6200)
        self.assertEqual(data['lecture_state']['messages'][0]['content'], 'Visible answer')
        self.assertEqual(RoadmapNode.objects.get(pk=old_loop_id).slug, 'loops')
        self.assertEqual(list(Submission.objects.values()), before_submissions)
        arrays = RoadmapNode.objects.get(roadmap=self.roadmap, slug='array-basics')
        strings = RoadmapNode.objects.get(roadmap=self.roadmap, slug='string-basics')
        self.assertTrue(NodeProblem.objects.filter(node=arrays, problem=self.problem_a).exists())
        self.assertTrue(NodeProblem.objects.filter(node=strings, problem=self.problem_b).exists())
        self.assertFalse(NodeProblem.objects.filter(node=arrays, problem=self.problem_b).exists())
        progress = get_progress_data(self.roadmap, self.learner, self.nodes['foundations'].pk)
        self.assertEqual(progress['subtree']['solved'], 1)
        self.assertEqual(progress['subtree']['total'], 3)
        self.assertFalse(ProblemType.objects.filter(name='programming-basics').exists())
        self.assertEqual(set(self.legacy_string.types.values_list('name', flat=True)), {'string-basics'})
        self.assertTrue(NodeProblem.objects.filter(node=strings, problem=self.legacy_string).exists())
        self.assertFalse(NodeProblem.objects.filter(node=arrays, problem=self.legacy_string).exists())
        self.assertEqual(PolygonTagMapping.objects.get(tag='functions').problem_type_id, self.custom_type.pk)
        snapshot = list(TopicLesson.objects.values())
        self.cutover(apply=True, development=True, user=self.staff.username)
        self.assertEqual(list(TopicLesson.objects.values()), snapshot)
        queries = RoadmapNode.objects.get(roadmap=self.roadmap, slug='queries')
        self.assertEqual(queries.parent.slug, 'range-queries')
        response = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug]),
            {'view': 'catalog', 'group': self.nodes['foundations'].pk}, HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)
        sections = response.context['explorer']['catalog_sections']
        self.assertEqual([[n['slug'] for n in s['nodes']] for s in sections], [
            ['io-basics', 'conditions', 'loops', 'functions', 'array-basics', 'string-basics', 'matrix-basics'],
            ['algorithmic-thinking', 'complexity', 'implementation'],
        ])

    def test_dry_run_and_non_development_apply_do_not_change_learning_data(self):
        before = list(TopicLesson.objects.values())
        self.cutover()
        self.assertEqual(list(TopicLesson.objects.values()), before)
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.cutover(apply=True, development=True, user=self.staff.username)
        self.assertEqual(list(TopicLesson.objects.values()), before)

    def test_dry_run_rejects_excluded_practice_and_lesson_collisions(self):
        source = PolygonProblem.objects.create(polygon_id=5002, owner='ms24', name='excluded',
            problem=self.problem_a, status=PolygonProblem.SKIPPED)
        with self.assertRaises(CommandError):
            self.cutover()
        source.delete()
        TopicLesson.objects.create(topic=self.nodes['implementation'].learning_topic,
            slug='numeric-safety', title='An authored lesson', body='Keep this body', status='PUBLISHED')
        with self.assertRaises(CommandError):
            self.cutover()

    def test_missing_delete_permission_refuses_cutover_without_writes(self):
        from django.contrib.auth.models import User
        from unittest.mock import patch
        before = list(TopicLesson.objects.values())
        with patch.object(User, 'has_perms', side_effect=lambda permissions: 'mentor.delete_nodeproblem' not in permissions):
            with self.assertRaises(CommandError):
                self.cutover(apply=True, development=True, user=self.staff.username)
        self.assertEqual(list(TopicLesson.objects.values()), before)

from threading import Barrier, Thread

from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from judge.models import Language, Organization, Problem, ProblemGroup, Profile, Submission
from .models import LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite, TopicLesson
from .roadmap_models import Publication, Visibility
from .roadmap_services import (create_node, delete_node, move_node, reorder_nodes, save_content,
                               save_node, save_problem_link)


class RoadmapFixture:
    def setUp(self):
        self.staff = User.objects.create_superuser('roadmap-staff', '', 'test-password')
        self.profile = Profile.objects.create(user=self.staff)
        self.learner = User.objects.create_user('roadmap-learner')
        self.learner_profile = Profile.objects.create(user=self.learner)
        self.roadmap = Roadmap.objects.create(title='CP', slug='cp', status=Publication.PUBLISHED)
        self.topic = LearningTopic.objects.create(name='Shared', slug='shared', introduction='Theory',
                                                  status=Publication.PUBLISHED)
        self.group = ProblemGroup.objects.create(name='roadmap', full_name='Roadmap')
        self.language = Language.objects.create(key='ROADMAP', name='Roadmap', common_name='Roadmap',
                                                ace='python', pygments='python', extension='py')

    def node(self, slug, **fields):
        learning_topic = fields.pop('learning_topic', self.topic)
        return create_node(self.staff, roadmap=self.roadmap, title=slug, slug=slug,
                           learning_topic=learning_topic, status=Publication.PUBLISHED, **fields)

    def problem(self, code, **fields):
        return Problem.objects.create(code=code, name=code, group=self.group, time_limit=1,
                                      memory_limit=65536, points=100, **{'is_public': True, **fields})

    def link(self, node, problem):
        return save_problem_link(self.staff, NodeProblem(node=node, problem=problem))

    def submission(self, problem, result='AC', **fields):
        return Submission.objects.create(user=self.learner_profile, problem=problem, language=self.language,
                                         result=result, status='D', **fields)


class RoadmapTreeTests(RoadmapFixture, TestCase):
    def test_deep_mixed_tree_cycle_and_cross_roadmap(self):
        root = self.node('root', type='TOPIC')
        parent = root
        for i in range(5):
            parent = self.node(f'deep-{i}', parent=parent, type='GROUP' if i % 2 == 0 else 'TOPIC')
        self.assertEqual(parent.get_ancestors().count(), 5)
        with self.assertRaises(ValidationError):
            move_node(self.staff, root.pk, parent.pk)
        with self.assertRaises(ValidationError):
            move_node(self.staff, root.pk, root.pk)
        other = Roadmap.objects.create(title='Other', slug='other')
        outside = create_node(self.staff, roadmap=other, title='Outside', slug='outside')
        with self.assertRaises(ValidationError):
            move_node(self.staff, parent.pk, outside.pk)
        root.refresh_from_db()
        self.assertIsNone(root.parent_id)

    def test_move_stale_instances_and_reorder_preserve_intervals(self):
        root = self.node('root')
        a = self.node('a', parent=root)
        b = self.node('b', parent=root)
        c = self.node('c', parent=a)
        stale = RoadmapNode.objects.get(pk=b.pk)
        move_node(self.staff, a.pk, None)
        stale.parent_id = a.pk
        save_node(self.staff, stale)
        c.refresh_from_db()
        self.assertEqual([n.pk for n in c.get_ancestors()], [a.pk])
        ordered = reorder_nodes(self.staff, self.roadmap.pk, a.pk, [b.pk, c.pk])
        self.assertEqual([n.pk for n in ordered], [b.pk, c.pk])
        with self.assertRaises(ValidationError):
            reorder_nodes(self.staff, self.roadmap.pk, a.pk, [b.pk, b.pk])
        for node in RoadmapNode.objects.all():
            self.assertEqual(node.get_ancestors().count(), node.level)

    def test_protect_tree_topic_problem_and_prerequisites(self):
        root = self.node('root')
        leaf = self.node('leaf', parent=root)
        problem = self.problem('protected_problem')
        self.link(leaf, problem)
        for obj in (root, self.roadmap, self.topic, problem):
            with self.assertRaises(ProtectedError):
                obj.delete()
        edge = RoadmapPrerequisite.objects.create(node=root, prerequisite=leaf)
        with self.assertRaises(ProtectedError):
            delete_node(self.staff, leaf.pk)
        edge.delete()
        delete_node(self.staff, leaf.pk)
        self.assertTrue(Problem.objects.filter(pk=problem.pk).exists())
        self.assertFalse(NodeProblem.objects.exists())

    def test_lesson_scope_revision_and_invalid_parent(self):
        lesson = TopicLesson.objects.create(topic=self.topic, title='Theory', slug='theory', body='Text',
                                           status=Publication.PUBLISHED)
        with self.assertRaises(ProtectedError):
            self.topic.delete()
        other = LearningTopic.objects.create(name='Other', slug='other', introduction='Intro')
        self.topic.refresh_from_db()
        revision = self.topic.content_revision
        lesson.topic = other
        lesson.save()
        self.topic.refresh_from_db()
        self.assertGreater(self.topic.content_revision, revision)
        self.assertEqual(lesson.topic_id, other.pk)
        with self.assertRaises(ValidationError):
            create_node(self.staff, roadmap=self.roadmap, title='Bad', slug='bad', parent_id=999999)
        with self.assertRaises(ValidationError):
            TopicLesson(topic=other, title='Empty', slug='empty', status=Publication.PUBLISHED).save()

    def test_exercises_only_node_link_move_allows_empty_published_source(self):
        source = create_node(self.staff, roadmap=self.roadmap, title='Exercises', slug='exercises')
        target = self.node('target')
        link = self.link(source, self.problem('only_exercise'))
        source.status = Publication.PUBLISHED
        save_node(self.staff, source)
        link.node = target
        save_problem_link(self.staff, link)
        link.refresh_from_db()
        self.assertEqual(link.node_id, target.pk)
        source.refresh_from_db()
        self.assertEqual(source.status, Publication.PUBLISHED)
        self.assertEqual(source.problem_links.count(), 0)
    def test_staff_permissions_publish_and_content_reuse(self):
        editor = User.objects.create_user('roadmap-editor', is_staff=True)
        editor.user_permissions.add(Permission.objects.get(codename='add_roadmapnode', content_type__app_label='mentor'))
        draft = create_node(editor, roadmap=self.roadmap, title='Draft', slug='draft', learning_topic=self.topic)
        draft.status = Publication.PUBLISHED
        with self.assertRaises(PermissionDenied):
            save_node(editor, draft)
        with self.assertRaises(PermissionDenied):
            create_node(self.learner, roadmap=self.roadmap, title='Forged', slug='forged')
        blank = LearningTopic.objects.create(name='Blank', slug='blank')
        empty_published = create_node(self.staff, roadmap=self.roadmap, title='Empty', slug='empty',
                                      learning_topic=blank, status=Publication.PUBLISHED)
        self.assertEqual(empty_published.status, Publication.PUBLISHED)
        exercise_only = create_node(self.staff, roadmap=self.roadmap, title='Exercises', slug='exercises')
        self.link(exercise_only, self.problem('exercise_only'))
        exercise_only.status = Publication.PUBLISHED
        save_node(self.staff, exercise_only)
        other = self.node('other')
        self.assertEqual(other.learning_topic_id, draft.learning_topic_id)
        old_revision = self.topic.content_revision
        self.topic.introduction = 'Updated theory'
        save_content(self.staff, self.topic)
        self.assertGreater(self.topic.content_revision, old_revision)
        org = Organization.objects.create(slug='roadmaporg', name='Roadmap org', short_name='RM', about='')
        private = LearningTopic.objects.create(name='Private', slug='private', visibility=Visibility.ORGANIZATION,
                                               organization=org, introduction='Private')
        with self.assertRaises(ValidationError):
            create_node(self.staff, roadmap=self.roadmap, title='Leak', slug='leak', learning_topic=private)


class RoadmapConcurrencyTests(RoadmapFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_opposite_concurrent_moves_allow_only_one(self):
        a, b = self.node('a'), self.node('b')
        barrier = Barrier(2)
        outcomes = []

        def move(source, target):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.staff.pk)
                barrier.wait(timeout=10)
                try:
                    move_node(actor, source, target)
                    outcomes.append('moved')
                except ValidationError:
                    outcomes.append('cycle')
            except Exception as exc:
                outcomes.append(type(exc).__name__)
            finally:
                close_old_connections()

        threads = [Thread(target=move, args=(a.pk, b.pk)), Thread(target=move, args=(b.pk, a.pk))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertCountEqual(outcomes, ['moved', 'cycle'])
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertNotEqual(a.parent_id == b.pk, b.parent_id == a.pk)

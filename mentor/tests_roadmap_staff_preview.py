from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.http import Http404

from judge.models import Profile
from .models import LearningTopic, Roadmap, RoadmapNode, TopicLesson, TopicLessonState
from .roadmap_models import Publication
from .roadmap_services import create_node
from .roadmap_staff_preview import get_roadmap_visibility, roadmap_staff_preview
from .tests_roadmap import RoadmapFixture


class RoadmapStaffPreviewTests(RoadmapFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.node_a = self.node('preview-node')
        self.lesson = TopicLesson.objects.create(
            topic=self.topic, title='Preview lesson', slug='preview-lesson',
            summary='A concise summary.', body='# Safe content\n\nLearner-facing body.',
            status=Publication.DRAFT,
        )
        self.factory = RequestFactory()

    def preview(self, user=None, **query):
        request = self.factory.get('/admin/', query)
        request.user = user or self.staff
        request.LANGUAGE_CODE = 'en'
        return roadmap_staff_preview(request, self.roadmap.pk, admin.site)

    def test_staff_preview_renders_draft_content_without_writing_learning_state(self):
        response = self.preview(node=self.node_a.pk, lesson=self.lesson.pk)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h3>Safe content</h3>')
        self.assertContains(response, 'A concise summary.')
        self.assertEqual(TopicLessonState.objects.count(), 0)
        self.assertFalse(response.has_header('Set-Cookie'))
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_requested_node_and_lesson_must_belong_to_selected_roadmap_topic(self):
        other_roadmap = Roadmap.objects.create(title='Other', slug='other-preview')
        other_node = create_node(self.staff, roadmap=other_roadmap, title='Other node', slug='other-node')
        with self.assertRaises(Http404):
            self.preview(node=other_node.pk)
        with self.assertRaises(Http404):
            self.preview(lesson=self.lesson.pk)

    def test_view_node_permission_does_not_grant_topic_content_permission(self):
        viewer = User.objects.create_user('preview-node-viewer', is_staff=True)
        Profile.objects.create(user=viewer)
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='mentor',
            codename__in=('view_roadmap', 'view_roadmapnode'),
        ))
        with self.assertRaises(PermissionDenied):
            self.preview(viewer, node=self.node_a.pk)

    def test_read_only_methods_and_inactive_staff_are_rejected(self):
        request = self.factory.post('/admin/')
        request.user = self.staff
        response = roadmap_staff_preview(request, self.roadmap.pk, admin.site)
        self.assertEqual(response.status_code, 405)
        inactive = User.objects.create_user('inactive-preview', is_staff=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            self.preview(inactive)

    def test_private_linked_problem_name_is_not_disclosed(self):
        private_problem = self.problem('preview-hidden-problem', is_public=False)
        self.link(self.node_a, private_problem)
        viewer = User.objects.create_user('preview-content-viewer', is_staff=True)
        Profile.objects.create(user=viewer)
        viewer.user_permissions.add(*Permission.objects.filter(content_type__app_label='mentor',
            codename__in=('view_roadmap', 'view_roadmapnode', 'view_learningtopic', 'view_topiclesson')))
        response = self.preview(viewer, node=self.node_a.pk)
        response.render()
        self.assertNotContains(response, private_problem.name)

    def test_visibility_helper_reports_inherited_draft_and_incomplete_content(self):
        parent = self.node('draft-parent', type=RoadmapNode.Type.GROUP)
        parent.status = Publication.DRAFT
        parent.save()
        child = self.node('child-under-draft', parent=parent)
        report = get_roadmap_visibility(self.roadmap, node=child)
        self.assertFalse(report['visible'])
        self.assertEqual(len(report['reasons']), 1)
        self.assertTrue(get_roadmap_visibility(self.roadmap)['visible'])

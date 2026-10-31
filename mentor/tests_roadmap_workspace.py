from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from judge.models import Profile
from .models import LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite, TopicLesson
from .tests_roadmap import RoadmapFixture


class RoadmapWorkspaceTests(RoadmapFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)
        self.a = self.node('workspace-a')
        self.b = self.node('workspace-b')

    def url(self, node=None, tab='information'):
        name = 'admin:mentor_roadmap_node_workspace' if node else 'admin:mentor_roadmap_workspace'
        args = [self.roadmap.pk, node.pk] if node else [self.roadmap.pk]
        return reverse(name, args=args) + f'?tab={tab}'

    def test_creation_builds_private_draft_content_and_moves_without_replacing_ids(self):
        add = reverse('admin:mentor_roadmap_node_add', args=[self.roadmap.pk])
        response = self.client.post(add, {'action': 'placement', 'title': 'Một chuyên đề mới',
            'kind': 'TOPIC', 'parent': self.a.pk, 'difficulty': 'BASIC', 'content_source': 'new'})
        self.assertEqual(response.status_code, 302)
        item = RoadmapNode.objects.get(title='Một chuyên đề mới')
        self.assertEqual(item.parent_id, self.a.pk)
        self.assertEqual(item.status, 'DRAFT')
        self.assertEqual(item.learning_topic.status, 'DRAFT')
        self.assertEqual(item.learning_topic.visibility, self.roadmap.visibility)
        topic_id = item.learning_topic_id
        response = self.client.post(self.url(item), {'action': 'placement', 'title': item.title,
            'slug': item.slug, 'parent': self.b.pk, 'summary': 'Short explanation'})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.parent_id, self.b.pk)
        self.assertEqual(item.learning_topic_id, topic_id)
        self.assertEqual(item.summary, 'Short explanation')

    def test_viewer_can_read_but_cannot_mutate_or_publish(self):
        viewer = User.objects.create_user('workspace-viewer', is_staff=True)
        Profile.objects.create(user=viewer)
        viewer.user_permissions.add(*Permission.objects.filter(content_type__app_label='mentor',
            codename__in=['view_roadmap', 'view_roadmapnode']))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url(self.a)).status_code, 200)
        response = self.client.post(self.url(self.a), {'action': 'placement', 'title': 'forged'})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(self.url(self.a, 'publication'),
            {'action': 'publication', 'target': 'node', 'status': 'DRAFT', 'confirm': 'on'})
        self.assertEqual(response.status_code, 403)
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, 'PUBLISHED')

    def test_shared_introduction_requires_confirmation_and_respects_topic_permission(self):
        before = self.topic.introduction
        payload = {'action': 'introduction', 'name': self.topic.name, 'introduction': 'Changed for both'}
        response = self.client.post(self.url(self.a), payload)
        self.assertEqual(response.status_code, 200)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.introduction, before)
        response = self.client.post(self.url(self.a), {**payload, 'confirm_shared': 'on'})
        self.assertEqual(response.status_code, 302)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.introduction, 'Changed for both')

    def test_prerequisites_reject_cycles_and_foreign_roadmap(self):
        response = self.client.post(self.url(self.b, 'prerequisites'),
            {'action': 'prerequisite_add', 'prerequisite': self.a.pk, 'reason': 'Learn A first'})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(self.url(self.a, 'prerequisites'),
            {'action': 'prerequisite_add', 'prerequisite': self.b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RoadmapPrerequisite.objects.filter(node=self.a).exists())
        other = Roadmap.objects.create(title='Other scope', slug='workspace-other')
        foreign = RoadmapNode.objects.create(roadmap=other, title='Other', slug='other')
        response = self.client.post(self.url(self.a, 'prerequisites'),
            {'action': 'prerequisite_add', 'prerequisite': foreign.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RoadmapPrerequisite.objects.filter(node=self.a).exists())

    def test_removing_practice_does_not_delete_problem_or_submission(self):
        problem = self.problem('workspace-practice')
        link = self.link(self.a, problem)
        submission = self.submission(problem)
        response = self.client.post(self.url(self.a, 'problems'),
            {'action': 'problem_remove', 'item': link.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(NodeProblem.objects.filter(pk=link.pk).exists())
        problem.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(submission.result, 'AC')

    def test_forged_reorder_cannot_touch_another_topic(self):
        own = TopicLesson.objects.create(topic=self.topic, title='Own', slug='own', body='body', position=8)
        outside = LearningTopic.objects.create(name='Outside', slug='outside-workspace')
        foreign = TopicLesson.objects.create(topic=outside, title='Foreign', slug='foreign', body='body', position=7)
        response = self.client.post(self.url(self.a, 'lessons'), {'action': 'reorder', 'target': 'lesson',
            'item': foreign.pk, 'direction': 'up', 'confirm_shared': 'on'})
        self.assertEqual(response.status_code, 200)
        foreign.refresh_from_db()
        own.refresh_from_db()
        self.assertEqual(foreign.position, 7)
        self.assertEqual(own.position, 8)

    def test_lesson_reorder_preserves_resume_and_qa_for_content_revision(self):
        from .models import TopicLessonQAMessage, TopicLessonState
        from .roadmap_selectors import get_node_lesson_data

        first = TopicLesson.objects.create(topic=self.topic, title='First', slug='first-order',
            body='First body', status='PUBLISHED', position=0)
        second = TopicLesson.objects.create(topic=self.topic, title='Second', slug='second-order',
            body='Second body', status='PUBLISHED', position=1)
        TopicLessonState.objects.create(user=self.learner, lesson=first,
            content_revision=first.content_revision, offset=6200)
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=first,
            content_revision=first.content_revision, role='user', content='Saved question')
        self.topic.refresh_from_db()
        revisions = (first.content_revision, second.content_revision, self.topic.content_revision)
        editor = User.objects.create_user('workspace-lesson-editor', is_staff=True)
        Profile.objects.create(user=editor)
        editor.user_permissions.add(*Permission.objects.filter(content_type__app_label='mentor',
            codename__in=['view_roadmap', 'view_roadmapnode', 'change_learningtopic', 'change_topiclesson']))
        self.client.force_login(editor)
        response = self.client.post(self.url(self.a, 'lessons'), {'action': 'reorder', 'target': 'lesson',
            'item': second.pk, 'direction': 'up', 'confirm_shared': 'on'})
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        self.topic.refresh_from_db()
        self.assertEqual((first.position, second.position), (1, 0))
        self.assertEqual((first.content_revision, second.content_revision, self.topic.content_revision), revisions)
        data = get_node_lesson_data(self.roadmap, self.a.pk, first.pk, self.learner)
        self.assertEqual(data['lecture_state']['resume_offset'], 6200)
        self.assertEqual(data['lecture_state']['messages'][0]['content'], 'Saved question')
        self.assertIn(str(second.pk), data['navigation']['prev_lesson_url'])

    def test_lesson_only_viewer_does_not_receive_workspace_titles_from_query(self):
        lesson = TopicLesson.objects.create(topic=self.topic, title='Read-only lesson',
            slug='read-only-workspace', body='Body')
        viewer = User.objects.create_user('workspace-lesson-only', is_staff=True)
        Profile.objects.create(user=viewer)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='mentor',
            codename='view_topiclesson'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('admin:mentor_topiclesson_change', args=[lesson.pk]),
            {'workspace_node': self.a.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('workspace_node', response.context_data)

    def test_failed_placement_keeps_saved_title_and_attaches_slug_error_to_field(self):
        response = self.client.post(self.url(self.a), {'action': 'placement', 'title': 'Unsaved title',
            'slug': '', 'parent': self.b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['node'].title, self.a.title)
        self.assertIn('slug', response.context_data['placement_form'].errors)

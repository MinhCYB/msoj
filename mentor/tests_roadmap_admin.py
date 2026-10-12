from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from judge.models import Profile

from .models import LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite
from .tests_roadmap import RoadmapFixture

class RoadmapAdminTests(RoadmapFixture, TestCase):
    inline_management = {'problem_links-TOTAL_FORMS': 0, 'problem_links-INITIAL_FORMS': 0,
                         'problem_links-MIN_NUM_FORMS': 0, 'problem_links-MAX_NUM_FORMS': 1000}

    def node_payload(self, node, **changes):
        return {'roadmap': node.roadmap_id, 'parent': node.parent_id or '',
                'learning_topic': node.learning_topic_id or '', 'title': node.title, 'slug': node.slug,
                'type': node.type, 'position': node.position, 'difficulty': node.difficulty or '',
                'status': node.status, '_save': 'Save', **self.inline_management, **changes}

    def test_admin_http_create_move_invalid_cycle_and_protect(self):
        self.client.force_login(self.staff)
        add = reverse('admin:mentor_roadmapnode_add')
        response = self.client.post(add, {'roadmap': self.roadmap.pk, 'parent': '',
                                         'learning_topic': self.topic.pk, 'title': 'Admin root', 'slug': 'admin-root',
                                         'type': 'TOPIC', 'position': 0, 'difficulty': 'BASIC',
                                         'status': 'PUBLISHED', '_save': 'Save', **self.inline_management})
        self.assertEqual(response.status_code, 302)
        root = RoadmapNode.objects.get(slug='admin-root')
        child = self.node('child', parent=root)
        change = reverse('admin:mentor_roadmapnode_change', args=[root.pk])
        invalid = self.client.post(change, self.node_payload(root, parent=child.pk))
        self.assertEqual(invalid.status_code, 200)
        root.refresh_from_db()
        self.assertIsNone(root.parent_id)
        child_change = reverse('admin:mentor_roadmapnode_change', args=[child.pk])
        moved = self.client.post(child_change, self.node_payload(child, parent='', position=3))
        self.assertEqual(moved.status_code, 302)
        child.refresh_from_db()
        self.assertIsNone(child.parent_id)
        self.client.post(child_change, self.node_payload(child, parent=root.pk))
        delete = self.client.post(reverse('admin:mentor_roadmapnode_delete', args=[root.pk]), {'post': 'yes'})
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(RoadmapNode.objects.filter(pk=root.pk).exists())

    def test_view_only_staff_and_forged_publication(self):
        node = self.node('draft')
        node.status = 'DRAFT'
        node.save()
        editor = User.objects.create_user('roadmap-admin-editor', is_staff=True)
        Profile.objects.create(user=editor)
        editor.user_permissions.add(*Permission.objects.filter(content_type__app_label='mentor',
                                                               codename__in=['view_roadmapnode', 'change_roadmapnode']))
        self.client.force_login(editor)
        change = reverse('admin:mentor_roadmapnode_change', args=[node.pk])
        self.assertEqual(self.client.get(change).status_code, 200)
        response = self.client.post(change, self.node_payload(node, status='PUBLISHED'))
        self.assertIn(response.status_code, (200, 302, 403))
        node.refresh_from_db()
        self.assertEqual(node.status, 'DRAFT')
        viewer = User.objects.create_user('roadmap-admin-viewer', is_staff=True)
        Profile.objects.create(user=viewer)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='mentor',
                                                           codename='view_roadmapnode'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(change).status_code, 200)
        self.assertEqual(self.client.post(change, self.node_payload(node, title='Forbidden')).status_code, 403)
        node.refresh_from_db()
        self.assertNotEqual(node.title, 'Forbidden')

    def test_problem_link_forged_private_pk_is_rejected(self):
        node = self.node('node')
        private = self.problem('admin_private', is_public=False)
        editor = User.objects.create_user('roadmap-link-editor', is_staff=True)
        Profile.objects.create(user=editor)
        editor.user_permissions.add(*Permission.objects.filter(content_type__app_label='mentor',
                                                               codename__in=['add_nodeproblem', 'change_roadmapnode']))
        self.client.force_login(editor)
        response = self.client.post(reverse('admin:mentor_nodeproblem_add'),
                                    {'node': node.pk, 'problem': private.pk, 'position': 0, '_save': 'Save'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NodeProblem.objects.filter(node=node, problem=private).exists())

    def test_prerequisite_admin_get_and_post_with_user_kw(self):
        self.client.force_login(self.staff)
        add_url = reverse('admin:mentor_roadmapprerequisite_add')
        resp_get = self.client.get(add_url)
        self.assertEqual(resp_get.status_code, 200)

        a = self.node('prereq-a')
        b = self.node('prereq-b')
        resp_post = self.client.post(add_url, {'node': b.pk, 'prerequisite': a.pk, '_save': 'Save'})
        self.assertEqual(resp_post.status_code, 302)
        self.assertTrue(RoadmapPrerequisite.objects.filter(node=b, prerequisite=a).exists())

        # Self-prerequisite is rejected by clean
        resp_self = self.client.post(add_url, {'node': a.pk, 'prerequisite': a.pk, '_save': 'Save'})
        self.assertEqual(resp_self.status_code, 200)

    def test_inline_last_exercise_deletion_and_replacement_allowed(self):
        self.client.force_login(self.staff)
        # Create a topic with NO theory (empty introduction, zero lessons)
        topic = LearningTopic.objects.create(name='Exercise Only', slug='exercise-only',
                                             introduction='', status='PUBLISHED')
        node = RoadmapNode.objects.create(roadmap=self.roadmap, title='Ex Topic', slug='ex-topic',
                                          learning_topic=topic, status='DRAFT', type='TOPIC')
        p1 = self.problem('ex-p1')
        p2 = self.problem('ex-p2')
        link1 = self.link(node, p1)
        node.status = 'PUBLISHED'
        node.save()

        change_url = reverse('admin:mentor_roadmapnode_change', args=[node.pk])

        # 1. Deleting last exercise WITHOUT replacement now succeeds (skeleton allowed)
        payload_delete_last = self.node_payload(
            node,
            learning_topic=topic.pk,
            **{
                'problem_links-TOTAL_FORMS': 1,
                'problem_links-INITIAL_FORMS': 1,
                'problem_links-MIN_NUM_FORMS': 0,
                'problem_links-MAX_NUM_FORMS': 1000,
                'problem_links-0-id': link1.pk,
                'problem_links-0-problem': p1.pk,
                'problem_links-0-position': 0,
                'problem_links-0-DELETE': 'on',
            }
        )
        resp_del_last = self.client.post(change_url, payload_delete_last)
        self.assertEqual(resp_del_last.status_code, 302)
        self.assertFalse(NodeProblem.objects.filter(pk=link1.pk).exists())
        node.refresh_from_db()
        self.assertEqual(node.status, 'PUBLISHED')

        # 2. Add an exercise then delete it via standalone admin delete view
        link2 = self.link(node, p2)
        standalone_del_url = reverse('admin:mentor_nodeproblem_delete', args=[link2.pk])
        resp_standalone_post = self.client.post(standalone_del_url, {'post': 'yes'})
        self.assertEqual(resp_standalone_post.status_code, 302)
        self.assertFalse(NodeProblem.objects.filter(pk=link2.pk).exists())
        node.refresh_from_db()
        self.assertEqual(node.status, 'PUBLISHED')

        # 3. Adding an exercise and replacing it with same problem atomically succeeds
        link3 = self.link(node, p1)
        payload_same_replace = self.node_payload(
            node,
            learning_topic=topic.pk,
            **{
                'problem_links-TOTAL_FORMS': 2,
                'problem_links-INITIAL_FORMS': 1,
                'problem_links-MIN_NUM_FORMS': 0,
                'problem_links-MAX_NUM_FORMS': 1000,
                'problem_links-0-id': link3.pk,
                'problem_links-0-problem': p1.pk,
                'problem_links-0-position': 0,
                'problem_links-0-DELETE': 'on',
                'problem_links-1-id': '',
                'problem_links-1-problem': p1.pk,
                'problem_links-1-position': 8,
            }
        )
        resp_same_replace = self.client.post(change_url, payload_same_replace)
        self.assertEqual(resp_same_replace.status_code, 302)
        node.refresh_from_db()
        self.assertEqual(node.status, 'PUBLISHED')
        updated_link = NodeProblem.objects.get(node=node)
        self.assertEqual(updated_link.problem_id, p1.pk)
        self.assertEqual(updated_link.position, 8)

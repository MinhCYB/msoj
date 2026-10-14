from django.test import TestCase
from django.urls import reverse

from .tests_roadmap import RoadmapFixture
from .roadmap_services import save_node


class RoadmapPageTests(RoadmapFixture, TestCase):
    def html(self, name, args, query=None):
        return self.client.get(reverse(name, args=args), query or {}, HTTP_ACCEPT='text/html')

    def test_node_icon_override_and_no_icon_reach_knowledge_cards(self):
        node = self.node('foundations', type='GROUP')
        for stored, displayed in [('', 'fa-code'), ('fa-database', 'fa-database'), ('none', '')]:
            with self.subTest(icon=stored):
                node.icon = stored
                save_node(self.staff, node)
                response = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'catalog'})
                self.assertEqual(response.context['explorer']['visible_nodes'][0]['icon_class'], displayed)

    def test_breadcrumb_tracks_selected_ancestry_not_catalog_or_goal_context(self):
        root = self.node('root', type='GROUP')
        nested = self.node('nested', type='GROUP', parent=root)
        selected = self.node('selected', parent=nested)
        other = self.node('other', type='GROUP')
        goal = self.node('goal', parent=other)
        for query in [
            {'view': 'catalog', 'group': other.pk, 'selected': selected.pk},
            {'view': 'path', 'goal': goal.pk, 'selected': selected.pk},
            {'focus': selected.pk},
        ]:
            with self.subTest(query=query):
                response = self.html('roadmap_detail', [self.roadmap.slug], query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([node['id'] for node in response.context['breadcrumb']],
                                 [root.pk, nested.pk, selected.pk])

    def test_breadcrumb_group_goal_and_catalog_root(self):
        root = self.node('root', type='GROUP')
        nested = self.node('nested', type='GROUP', parent=root)
        topic = self.node('topic', parent=nested)
        for query, expected in [
            ({'view': 'catalog', 'group': nested.pk}, [root.pk, nested.pk]),
            ({'view': 'path', 'goal': topic.pk}, [root.pk, nested.pk, topic.pk]),
            ({'view': 'catalog'}, []),
        ]:
            with self.subTest(query=query):
                response = self.html('roadmap_detail', [self.roadmap.slug], query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([node['id'] for node in response.context['breadcrumb']], expected)

    def test_html_focus_keeps_authorized_children_and_json_contract(self):
        root = self.node('root', type='GROUP')
        child = self.node('child', parent=root)
        draft = self.node('draft', parent=root)
        draft.status = 'DRAFT'
        save_node(self.staff, draft)
        self.node('hidden-descendant', parent=draft)
        response = self.html('roadmap_detail', [self.roadmap.slug], {'focus': root.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
        self.assertEqual([node['id'] for node in response.context['explorer']['visible_nodes']], [child.pk])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'focus': draft.pk}).status_code, 404)
        json_response = self.html('roadmap_detail', [self.roadmap.slug], {'format': 'json'})
        self.assertEqual(json_response.json()['items'][0]['id'], root.pk)
        self.assertEqual(self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug])).json()['items'][0]['id'], root.pk)

    def test_guest_has_no_fake_ac_and_cursor_is_bound_to_focused_parent(self):
        a, b = self.node('a'), self.node('b')
        for i in range(3):
            self.node(f'child-{i}', parent=a, position=i)
        cursor = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, a.pk]), {'limit': 1}).json()['next_cursor']
        response = self.html('roadmap_detail', [self.roadmap.slug], {'focus': b.pk, 'cursor': cursor})
        self.assertEqual(response.status_code, 400)
        guest = self.html('roadmap_detail', [self.roadmap.slug])
        self.assertEqual([item['progress']['state'] for item in guest.context['nodes']],
                         ['anonymous', 'anonymous'])
        self.roadmap.status = 'DRAFT'
        self.roadmap.save()
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug]).status_code, 404)

    def test_selected_node_detail_readiness_and_learn_cta(self):
        from .models import LearningTopic

        # 1. Upcoming / skeleton node: empty topic, 0 problems
        empty_topic = LearningTopic.objects.create(name='Skeleton Topic', slug='skeleton-topic',
                                                   introduction='', status='PUBLISHED')
        skel = self.node('skel-node', learning_topic=empty_topic)

        # 2. Available node: self.topic has 'Topic intro'
        ready = self.node('ready-node')

        # Test selecting upcoming node
        resp_skel = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'catalog', 'selected': skel.pk})
        self.assertEqual(resp_skel.status_code, 200)
        exp_skel = resp_skel.context['explorer']
        self.assertIsNotNone(exp_skel['selected'])
        self.assertEqual(exp_skel['selected']['id'], skel.pk)
        self.assertEqual(exp_skel['selected']['content_state'], 'UPCOMING')
        self.assertIsNone(exp_skel['selected']['learn_url'])

        # Test selecting available node
        resp_ready = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'catalog', 'selected': ready.pk})
        self.assertEqual(resp_ready.status_code, 200)
        exp_ready = resp_ready.context['explorer']
        self.assertIsNotNone(exp_ready['selected'])
        self.assertEqual(exp_ready['selected']['id'], ready.pk)
        self.assertEqual(exp_ready['selected']['content_state'], 'AVAILABLE')
        expected_learn_url = reverse('roadmap_node_learn', args=[self.roadmap.slug, ready.pk])
        self.assertEqual(exp_ready['selected']['learn_url'], expected_learn_url)

    def test_prerequisites_do_not_replace_default_catalog_with_a_goal_path(self):
        from .models import RoadmapPrerequisite

        group = self.node('foundations', type='GROUP')
        foundation = self.node('basics', parent=group)
        target = self.node('target', parent=group)
        RoadmapPrerequisite.objects.create(node=target, prerequisite=foundation)

        response = self.html('roadmap_detail', [self.roadmap.slug])
        self.assertEqual(response.status_code, 200)
        explorer = response.context['explorer']
        self.assertEqual(explorer['mode'], 'catalog')
        self.assertIsNone(explorer['goal'])
        self.assertEqual([node['id'] for node in explorer['visible_nodes']], [group.pk])

        path = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'path', 'goal': target.pk})
        self.assertEqual(path.status_code, 200)
        self.assertEqual(path.context['explorer']['mode'], 'path')
        self.assertEqual(path.context['explorer']['goal']['id'], target.pk)
        self.assertEqual([[node['id'] for node in stage['nodes']]
                          for stage in path.context['explorer']['stages']], [[foundation.pk], [target.pk]])

    def test_dag_prerequisites_cross_group_staged_order(self):
        from .models import RoadmapPrerequisite

        g1 = self.node('group-1', type='GROUP')
        t1 = self.node('topic-a', parent=g1)
        g2 = self.node('group-2', type='GROUP')
        t2 = self.node('topic-b', parent=g2)
        g3 = self.node('group-3', type='GROUP')
        t3 = self.node('topic-c', parent=g3)

        RoadmapPrerequisite.objects.create(node=t2, prerequisite=t1)
        RoadmapPrerequisite.objects.create(node=t3, prerequisite=t2)

        resp = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'path', 'goal': t3.pk})
        self.assertEqual(resp.status_code, 200)
        exp = resp.context['explorer']
        self.assertEqual(exp['mode'], 'path')
        self.assertEqual(exp['goal']['id'], t3.pk)
        self.assertTrue(exp['has_path'])
        self.assertEqual(len(exp['stages']), 3)
        self.assertEqual([n['id'] for n in exp['stages'][0]['nodes']], [t1.pk])
        self.assertEqual([n['id'] for n in exp['stages'][1]['nodes']], [t2.pk])
        self.assertEqual([n['id'] for n in exp['stages'][2]['nodes']], [t3.pk])

    def test_hidden_ancestor_prerequisite_never_leaks_and_breaks_path(self):
        from .models import RoadmapPrerequisite

        draft = self.node('draft-root', type='GROUP')
        draft.status = 'DRAFT'
        save_node(self.staff, draft)
        hidden_prereq = self.node('hidden-prereq', parent=draft)
        visible_prereq = self.node('visible-prereq')
        pub_topic = self.node('pub-topic')

        RoadmapPrerequisite.objects.create(node=pub_topic, prerequisite=hidden_prereq)
        RoadmapPrerequisite.objects.create(node=pub_topic, prerequisite=visible_prereq)

        resp = self.html('roadmap_detail', [self.roadmap.slug], {'view': 'path', 'goal': pub_topic.pk, 'selected': pub_topic.pk})
        self.assertEqual(resp.status_code, 200)
        exp = resp.context['explorer']
        self.assertFalse(exp['has_path'])
        self.assertNotIn(hidden_prereq.pk, [n['id'] for n in exp['visible_nodes']])
        # Missing prerequisite rows are omitted entirely; visible prerequisite reason is cleared
        self.assertEqual(len(exp['prerequisites']), 1)
        self.assertEqual(exp['prerequisites'][0]['node']['id'], visible_prereq.pk)
        self.assertEqual(exp['prerequisites'][0]['reason'], '')
        self.assertNotContains(resp, 'hidden-prereq')
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'goal': hidden_prereq.pk}).status_code, 404)

    def test_manifest_reason_does_not_disclose_hidden_prerequisite(self):
        from unittest.mock import patch
        from .roadmap_curriculum import ROADMAP_SLUG
        from .roadmap_models import Visibility

        self.roadmap.slug = ROADMAP_SLUG
        self.roadmap.visibility = Visibility.PUBLIC
        self.roadmap.save()
        visible = self.node('visible-foundation')
        target = self.node('visible-target')
        edges = [{'target': target.slug,
                  'prerequisites': [visible.slug, 'hidden-foundation'],
                  'reason': 'Private hidden-foundation dependency rationale'}]
        with patch('mentor.roadmap_explorer.get_manifest_prerequisite_edges', return_value=edges):
            response = self.html('roadmap_detail', [self.roadmap.slug],
                                 {'view': 'path', 'goal': target.pk, 'selected': target.pk})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['explorer']['has_path'])
            self.assertNotContains(response, 'hidden-foundation')
            self.assertEqual(response.context['explorer']['prerequisites'][0]['node']['id'], visible.pk)
            successor_response = self.html('roadmap_detail', [self.roadmap.slug],
                                           {'view': 'path', 'goal': target.pk, 'selected': visible.pk})
            self.assertNotContains(successor_response, 'hidden-foundation')

    def test_invalid_parameters_return_400(self):
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'view': 'invalid'}).status_code, 400)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'goal': 'invalid'}).status_code, 400)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'stage': '-1'}).status_code, 400)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'selected': 'invalid'}).status_code, 400)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'group': 'invalid'}).status_code, 400)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'selected': 999999}).status_code, 404)
        self.assertEqual(self.html('roadmap_detail', [self.roadmap.slug], {'group': 999999}).status_code, 404)

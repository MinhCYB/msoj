from django.test import TestCase
from django.urls import reverse

from .tests_roadmap import RoadmapFixture
from .roadmap_services import save_node


class RoadmapPageTests(RoadmapFixture, TestCase):
    def html(self, name, args, query=None):
        return self.client.get(reverse(name, args=args), query or {}, HTTP_ACCEPT='text/html')

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
        self.assertContains(response, f'data-node-id="{child.pk}"')
        self.assertNotContains(response, 'data-title="draft"')
        self.assertNotContains(response, 'data-title="hidden-descendant"')
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

    def test_ssr_skeleton_badge_and_learn_anchor(self):
        from lxml import html
        from .models import LearningTopic

        # 1. Upcoming / skeleton node: empty topic, 0 problems
        empty_topic = LearningTopic.objects.create(name='Skeleton Topic', slug='skeleton-topic',
                                                   introduction='', status='PUBLISHED')
        skel = self.node('skel-node', learning_topic=empty_topic)

        # 2. Available node: self.topic has 'Topic intro'
        ready = self.node('ready-node')

        response = self.html('roadmap_detail', [self.roadmap.slug])
        self.assertEqual(response.status_code, 200)

        tree = html.fromstring(response.content)
        skel_li = tree.xpath(f'//li[@data-node-id="{skel.pk}"]')[0]
        ready_li = tree.xpath(f'//li[@data-node-id="{ready.pk}"]')[0]

        # Skeleton node:
        # dataset content-state is UPCOMING
        self.assertEqual(skel_li.attrib.get('data-content-state'), 'UPCOMING')
        skel_badge = skel_li.xpath('.//span[contains(@class, "rm-content-status")]')[0]
        # Badge is visible (NOT hidden)
        self.assertNotIn('hidden', skel_badge.attrib)
        self.assertEqual(skel_badge.text_content().strip(), 'Sắp cập nhật')
        # Learn anchor is hidden (no active learn anchor)
        skel_learn = skel_li.xpath('.//a[contains(@class, "rm-learn")]')[0]
        self.assertIn('hidden', skel_learn.attrib)
        self.assertIsNone(skel_learn.attrib.get('href'))

        # Available node:
        # dataset content-state is AVAILABLE
        self.assertEqual(ready_li.attrib.get('data-content-state'), 'AVAILABLE')
        ready_badge = ready_li.xpath('.//span[contains(@class, "rm-content-status")]')[0]
        # Badge is hidden
        self.assertIn('hidden', ready_badge.attrib)
        # Learn anchor is active (not hidden, has href)
        ready_learn = ready_li.xpath('.//a[contains(@class, "rm-learn")]')[0]
        self.assertNotIn('hidden', ready_learn.attrib)
        expected_learn_url = reverse('roadmap_node_learn', args=[self.roadmap.slug, ready.pk])
        self.assertEqual(ready_learn.attrib.get('href'), expected_learn_url)

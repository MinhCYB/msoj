"""Focused behavior tests for Roadmap Explorer."""
from django.test import SimpleTestCase, TestCase

from .models import Roadmap, RoadmapNode, RoadmapPrerequisite
from .roadmap_curriculum import ROADMAP_SLUG
from .roadmap_explorer import (
    build_prerequisite_graphs,
    compute_goal_closure_and_stages,
    find_default_goal,
    get_serialized_published_nodes,
    order_goals_topological,
)
from .roadmap_models import Publication, Visibility
from .roadmap_services import save_node
from .tests_roadmap import RoadmapFixture


class RoadmapJourneyTests(SimpleTestCase):
    def test_only_supplied_roots_appear_and_nested_group_keeps_its_milestone(self):
        from .roadmap_explorer import _build_group_journey

        nodes = [
            {'id': 1, 'slug': 'foundations', 'type': 'GROUP', 'parent_id': None},
            {'id': 2, 'slug': 'graphs', 'type': 'GROUP', 'parent_id': None},
            {'id': 3, 'slug': 'nested', 'type': 'GROUP', 'parent_id': 2},
            {'id': 4, 'slug': 'topic', 'type': 'TOPIC', 'parent_id': 3},
            {'id': 5, 'slug': 'contest-skills', 'type': 'GROUP', 'parent_id': None},
            {'id': 6, 'slug': 'additional-group', 'type': 'GROUP', 'parent_id': None},
        ]
        journey, parallel, current = _build_group_journey(nodes, nodes[2], True)
        self.assertEqual([[node['id'] for node in stage['nodes']] for stage in journey], [[1], [2]])
        self.assertEqual([node['id'] for node in parallel], [5, 6])
        self.assertEqual(current['number'], 3)
        self.assertEqual(_build_group_journey(nodes, nodes[2], False), ([], [], None))

    def test_finder_uses_only_supplied_ancestors_and_scopes_aliases_to_curriculum(self):
        from .roadmap_explorer import _prepare_topic_finder

        nodes = [
            {'id': 1, 'slug': 'data-structures', 'title': 'Data structures', 'type': 'GROUP', 'parent_id': None},
            {'id': 2, 'slug': 'range-queries', 'title': 'Range queries', 'type': 'GROUP', 'parent_id': 1},
            {'id': 3, 'slug': 'segment-tree', 'title': 'Segment tree', 'type': 'TOPIC', 'parent_id': 2},
            {'id': 4, 'slug': 'orphan', 'title': 'Orphan', 'type': 'TOPIC', 'parent_id': 99},
        ]
        _prepare_topic_finder(nodes, True)
        self.assertEqual(nodes[2]['finder_path'], 'Data structures → Range queries')
        self.assertEqual(nodes[2]['finder_group'], 1)
        self.assertIn('cây đoạn', nodes[2]['finder_aliases'])
        self.assertEqual(nodes[3]['finder_path'], '')
        self.assertEqual(nodes[3]['finder_group'], '')
        _prepare_topic_finder(nodes, False)
        self.assertEqual(nodes[2]['finder_aliases'], [])


class RoadmapExplorerUnitTests(TestCase):
    def test_topological_ordering_prerequisites_before_dependents(self):
        nodes = [
            {'id': 1, 'slug': 'dfs', 'type': 'TOPIC', 'position': 0},
            {'id': 2, 'slug': 'recursion', 'type': 'TOPIC', 'position': 1},
            {'id': 3, 'slug': 'functions', 'type': 'TOPIC', 'position': 2},
        ]
        # dfs requires recursion; recursion requires functions
        prereq_graph = {
            1: [(2, 'reason')],
            2: [(3, 'reason')],
        }
        successor_graph = {
            3: [(2, 'reason')],
            2: [(1, 'reason')],
        }
        ordered = order_goals_topological(nodes, prereq_graph, successor_graph)
        ordered_ids = [n['id'] for n in ordered]
        self.assertEqual(ordered_ids, [3, 2, 1])

    def test_dfs_closure_staging_and_slug_layers(self):
        nodes = {
            1: {'id': 1, 'slug': 'functions', 'position': 0},
            2: {'id': 2, 'slug': 'stack', 'position': 1},
            3: {'id': 3, 'slug': 'graph-models', 'position': 2},
            4: {'id': 4, 'slug': 'recursion', 'position': 3},
            5: {'id': 5, 'slug': 'dfs', 'position': 4},
        }
        prereq_graph = {
            5: [(4, 'r1'), (2, 'r2'), (3, 'r3')],
            4: [(1, 'r4')],
        }
        stages, has_path = compute_goal_closure_and_stages(
            5, nodes, prereq_graph, missing_prereqs={}
        )
        self.assertTrue(has_path)
        self.assertEqual(len(stages), 3)

        stage_0_slugs = [n['slug'] for n in stages[0]['nodes']]
        self.assertEqual(sorted(stage_0_slugs), ['functions', 'graph-models', 'stack'])
        stage_1_slugs = [n['slug'] for n in stages[1]['nodes']]
        self.assertEqual(stage_1_slugs, ['recursion'])
        stage_2_slugs = [n['slug'] for n in stages[2]['nodes']]
        self.assertEqual(stage_2_slugs, ['dfs'])

    def test_cycle_detection_breaks_path_gracefully(self):
        nodes = {
            1: {'id': 1, 'slug': 'cycle-a', 'position': 0},
            2: {'id': 2, 'slug': 'cycle-b', 'position': 1},
        }
        # 1 requires 2, 2 requires 1
        prereq_graph = {
            1: [(2, 'r')],
            2: [(1, 'r')],
        }
        stages, has_path = compute_goal_closure_and_stages(
            1, nodes, prereq_graph, missing_prereqs={}
        )
        self.assertFalse(has_path)
        self.assertEqual(len(stages), 1)

    def test_missing_prerequisite_breaks_path(self):
        nodes = {
            1: {'id': 1, 'slug': 'target', 'position': 0},
        }
        stages, has_path = compute_goal_closure_and_stages(
            1, nodes, prereq_graph={}, missing_prereqs={1: [{'slug': 'missing', 'reason': 'test'}]}
        )
        self.assertFalse(has_path)


class RoadmapExplorerIntegrationTests(RoadmapFixture, TestCase):
    def test_get_serialized_published_nodes_bounds_and_excludes_draft(self):
        root = self.node('root-pub', type='GROUP')
        c1 = self.node('c1-pub', parent=root)
        draft = self.node('draft-root', type='GROUP')
        draft.status = Publication.DRAFT
        save_node(self.staff, draft)
        c2 = self.node('c2-hidden', parent=draft)

        serialized = get_serialized_published_nodes(self.roadmap, self.learner)
        serialized_ids = [n['id'] for n in serialized]
        self.assertIn(root.pk, serialized_ids)
        self.assertIn(c1.pk, serialized_ids)
        self.assertNotIn(draft.pk, serialized_ids)
        self.assertNotIn(c2.pk, serialized_ids)

    def test_noncanonical_roadmap_reads_db_prerequisites_only(self):
        t1 = self.node('topic-1')
        t2 = self.node('topic-2')
        RoadmapPrerequisite.objects.create(node=t2, prerequisite=t1)

        serialized = get_serialized_published_nodes(self.roadmap, self.learner)
        prereq_graph, successor_graph, missing_prereqs, is_canonical = build_prerequisite_graphs(
            self.roadmap, serialized
        )
        self.assertFalse(is_canonical)
        self.assertIn(t2.pk, prereq_graph)
        self.assertEqual(prereq_graph[t2.pk][0][0], t1.pk)
        self.assertIn(t1.pk, successor_graph)
        self.assertEqual(successor_graph[t1.pk][0][0], t2.pk)

    def test_canonical_cp_uses_database_edge_and_reason_without_manifest_override(self):
        from .roadmap_models import RoadmapPrerequisite

        self.roadmap.slug = ROADMAP_SLUG
        self.roadmap.visibility = Visibility.PUBLIC
        self.roadmap.save()
        first = self.node('custom-prior')
        second = self.node('custom-target', summary='Database summary')
        RoadmapPrerequisite.objects.create(node=second, prerequisite=first, reason='Database reason')
        serialized = get_serialized_published_nodes(self.roadmap, self.learner)
        prereq_graph, _, _, canonical = build_prerequisite_graphs(self.roadmap, serialized)
        self.assertTrue(canonical)
        self.assertEqual(prereq_graph[second.pk], [(first.pk, 'Database reason')])
        self.assertEqual(next(node for node in serialized if node['id'] == second.pk)['summary'], 'Database summary')

    def test_prerequisite_clean_rejects_reverse_cycle_and_cross_roadmap_edge(self):
        from django.core.exceptions import ValidationError

        first = self.node('cycle-first')
        second = self.node('cycle-second')
        RoadmapPrerequisite.objects.create(node=first, prerequisite=second)
        with self.assertRaises(ValidationError):
            RoadmapPrerequisite(node=second, prerequisite=first).full_clean()
        other_roadmap = Roadmap.objects.create(title='Other', slug='other-roadmap')
        cross_node = RoadmapNode.objects.create(roadmap=other_roadmap, title='Cross', slug='cross')
        with self.assertRaises(ValidationError):
            RoadmapPrerequisite(node=first, prerequisite=cross_node).full_clean()
    def test_canonical_cp_picks_dfs_when_complete(self):
        cp_roadmap = Roadmap.objects.create(
            title='Competitive Programming',
            slug=ROADMAP_SLUG,
            visibility=Visibility.PUBLIC,
            status=Publication.PUBLISHED,
        )
        from .roadmap_curriculum import load_curriculum_manifest
        for spec in load_curriculum_manifest()['nodes']:
            if spec['type'] == 'TOPIC':
                RoadmapNode.objects.create(roadmap=cp_roadmap, title=spec['title'], slug=spec['slug'],
                                          position=spec['position'], status=Publication.PUBLISHED)
        nodes_by_slug = {node.slug: node for node in RoadmapNode.objects.filter(roadmap=cp_roadmap)}
        for edge in load_curriculum_manifest()['prerequisites']['edges']:
            target = nodes_by_slug[edge['target']]
            for prior_slug in edge['prerequisites']:
                RoadmapPrerequisite.objects.create(
                    node=target, prerequisite=nodes_by_slug[prior_slug], reason=edge.get('reason', ''))

        serialized = get_serialized_published_nodes(cp_roadmap, self.learner)
        id_map = {n['id']: n for n in serialized}
        slug_map = {n['slug']: n for n in serialized}
        topic_nodes = [n for n in serialized if n['type'] == 'TOPIC']

        prereq_graph, successor_graph, missing_prereqs, is_canonical = build_prerequisite_graphs(
            cp_roadmap, serialized
        )
        self.assertTrue(is_canonical)
        default_goal = find_default_goal(
            cp_roadmap, topic_nodes, id_map, slug_map, prereq_graph, missing_prereqs, is_canonical
        )
        self.assertIsNotNone(default_goal)
        self.assertEqual(default_goal['slug'], 'dfs')

        stages, has_path = compute_goal_closure_and_stages(
            default_goal['id'], id_map, prereq_graph, missing_prereqs
        )
        self.assertTrue(has_path)
        layer = {node['id']: index for index, stage in enumerate(stages) for node in stage['nodes']}
        for node_id in layer:
            for prerequisite_id, reason in prereq_graph.get(node_id, []):
                self.assertLess(layer[prerequisite_id], layer[node_id])

from copy import deepcopy

from django.test import SimpleTestCase, TestCase

from judge.models import PolygonTagMapping, ProblemGroup, ProblemType
from judge.utils.polygon_sync import map_tags
from mentor.polygon_tag_mapping import PolygonTagMapError, apply_plan, build_plan, load_tag_map


class PolygonTagMapFileTests(SimpleTestCase):
    def test_shipped_map_resolves_against_the_curriculum_and_fits_the_columns(self):
        plan = build_plan()
        self.assertGreater(len(plan), 50)
        self.assertEqual(len({entry['tag'] for entry in plan}), len(plan))

    def test_unknown_node_is_reported(self):
        tag_map = deepcopy(load_tag_map())
        tag_map['tags']['dp'] = 'no-such-node'
        with self.assertRaisesMessage(PolygonTagMapError, "unknown roadmap node 'no-such-node'"):
            build_plan(tag_map)

    def test_name_longer_than_column_is_reported_instead_of_truncated_by_mysql(self):
        tag_map = deepcopy(load_tag_map())
        tag_map['type_names'].pop('binary-exponentiation')
        with self.assertRaisesMessage(PolygonTagMapError, 'binary-exponentiation'):
            build_plan(tag_map)

    def test_tag_cannot_be_mapped_and_unmapped(self):
        tag_map = deepcopy(load_tag_map())
        tag_map['unmapped']['dp'] = 'oops'
        with self.assertRaisesMessage(PolygonTagMapError, 'both mapped and unmapped'):
            build_plan(tag_map)

    def test_group_is_the_top_level_roadmap_domain_and_type_is_the_node_title(self):
        entry = next(e for e in build_plan() if e['tag'] == 'dijkstra')
        self.assertEqual(entry['type'], ('dijkstra', 'Dijkstra'))
        self.assertEqual(entry['group'][0], 'graphs')

    def test_foundation_tags_map_to_canonical_topics(self):
        mapped = load_tag_map()['tags']
        self.assertEqual(mapped['basic'], 'implementation')
        self.assertEqual(mapped['ifelse'], 'conditions')
        self.assertEqual(mapped['array'], 'array-basics')
        self.assertEqual(mapped['2d array'], 'matrix-basics')
        self.assertEqual(mapped['string'], 'string-basics')
        self.assertEqual(mapped['strings'], 'string-basics')


class ApplyPlanTests(TestCase):
    def test_apply_is_idempotent_and_keeps_admin_edits(self):
        plan = build_plan()
        first = apply_plan(plan)
        self.assertEqual(len(first['mappings']), len(plan))

        ProblemType.objects.filter(name='dijkstra').update(full_name='Đường đi Dijkstra')
        PolygonTagMapping.objects.filter(tag='dijkstra').update(problem_group=None)
        second = apply_plan(plan)

        self.assertEqual(second, {'types': [], 'groups': [], 'mappings': []})
        self.assertEqual(ProblemType.objects.get(name='dijkstra').full_name, 'Đường đi Dijkstra')
        self.assertIsNone(PolygonTagMapping.objects.get(tag='dijkstra').problem_group)

    def test_synced_problem_gets_type_and_group_from_its_tags(self):
        apply_plan(build_plan())
        group, types = map_tags(['cyb-boclot', 'Dijkstra', 'dsu'])
        self.assertEqual(group, ProblemGroup.objects.get(name='graphs'))
        self.assertEqual({t.name for t in types}, {'dijkstra', 'dsu'})

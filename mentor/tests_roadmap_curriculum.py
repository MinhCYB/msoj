"""Unit and integration tests for curriculum manifest, seeder command, and safety guards."""
from copy import deepcopy
import io
import tempfile
from django.contrib.auth.models import Permission, User
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from judge.models import Organization, Problem, ProblemGroup, Profile
from mentor.models import (
    LearningTopic,
    NodeProblem,
    Roadmap,
    RoadmapNode,
    RoadmapPrerequisite,
    TopicLesson,
)
from mentor.roadmap_curriculum import (
    ROADMAP_SLUG,
    CurriculumValidationError,
    load_curriculum_manifest,
    validate_curriculum_manifest,
)
from mentor.roadmap_models import Publication, Visibility
from mentor.roadmap_services import create_node, save_problem_link


class CurriculumManifestBehaviorTests(TestCase):
    """Test manifest validation invariants and typed error rejection on corrupted shapes."""

    def setUp(self):
        super().setUp()
        self.manifest = load_curriculum_manifest()

    def test_validation_rejects_malformed_shapes_with_typed_error(self):
        # 1. Non-dict root
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest("invalid_string_root")

        # 2. Non-dict roadmap
        bad = deepcopy(self.manifest)
        bad['roadmap'] = 'invalid_roadmap_string'
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 3. Non-list nodes
        bad = deepcopy(self.manifest)
        bad['nodes'] = {'slug': 'single_node'}
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 4. Non-dict node entry
        bad = deepcopy(self.manifest)
        bad['nodes'][0] = 'not_a_dictionary'
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 5. Non-string slug or title
        bad = deepcopy(self.manifest)
        bad['nodes'][0]['slug'] = 12345
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['nodes'][0]['title'] = None
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 6. Non-integer position
        bad = deepcopy(self.manifest)
        bad['nodes'][0]['position'] = "zero"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 7. Non-dict prerequisites or non-list edges
        bad = deepcopy(self.manifest)
        bad['prerequisites'] = "not_dict"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['prerequisites']['edges'] = "not_list"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 8. Non-dict edge or non-list priors
        bad = deepcopy(self.manifest)
        bad['prerequisites']['edges'][0] = "not_edge_dict"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['prerequisites']['edges'][0]['prerequisites'] = "not_a_list"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 9. Non-dict crosswalk or non-list topics
        bad = deepcopy(self.manifest)
        bad['crosswalk'] = "not_dict"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['crosswalk']['r_topics'] = "not_list"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['crosswalk']['r_topics'][0] = "not_topic_dict"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        bad['crosswalk']['r_topics'][0]['slugs'] = "not_slug_list"
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 10. Missing required node keys 'parent' and 'difficulty'
        bad = deepcopy(self.manifest)
        del bad['nodes'][0]['parent']
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        bad = deepcopy(self.manifest)
        del bad['nodes'][1]['difficulty']
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 11. Null crosswalk collection
        bad = deepcopy(self.manifest)
        bad['crosswalk']['r_topics'] = None
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # 12. Non-string slug in crosswalk
        bad = deepcopy(self.manifest)
        bad['crosswalk']['r_topics'][0]['slugs'] = [{'not': 'string'}]
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)
    def test_validation_rejects_corrupted_manifest_invariants(self):
        # Corrupted node count
        bad = deepcopy(self.manifest)
        bad['nodes'].pop()
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Corrupted root count/type
        bad = deepcopy(self.manifest)
        bad['nodes'][0]['parent'] = 'basic-algorithms'
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Sibling position gap
        bad = deepcopy(self.manifest)
        bad['nodes'][1]['position'] = 99
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Parent hierarchy cycle
        bad = deepcopy(self.manifest)
        bad['nodes'][0]['parent'] = bad['nodes'][1]['slug']
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Depth > 4
        bad = deepcopy(self.manifest)
        bad['nodes'][1]['parent'] = bad['nodes'][0]['slug']  # depth 2
        bad['nodes'][2]['parent'] = bad['nodes'][1]['slug']  # depth 3
        bad['nodes'][3]['parent'] = bad['nodes'][2]['slug']  # depth 4
        bad['nodes'][4]['parent'] = bad['nodes'][3]['slug']  # depth 5
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Invalid difficulty for GROUP
        bad = deepcopy(self.manifest)
        bad['nodes'][0]['difficulty'] = 'BASIC'
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Cycle in prerequisite graph
        bad = deepcopy(self.manifest)
        bad['prerequisites']['edges'].append({
            'target': 'programming-basics',
            'prerequisites': ['complexity'],
            'reason': 'Artificial cycle',
        })
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Unknown slug in prerequisite
        bad = deepcopy(self.manifest)
        bad['prerequisites']['edges'][0]['target'] = 'nonexistent-target'
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Count-preserving duplicate prerequisite target
        bad = deepcopy(self.manifest)
        # edge 0 has target 'complexity' with 1 prior; edge 1 has target 'recursion' with 1 prior
        bad['prerequisites']['edges'][1]['target'] = bad['prerequisites']['edges'][0]['target']
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)

        # Duplicate prior within target record
        bad = deepcopy(self.manifest)
        first_prior = bad['prerequisites']['edges'][2]['prerequisites'][0]
        bad['prerequisites']['edges'][2]['prerequisites'].append(first_prior)
        with self.assertRaises(CurriculumValidationError):
            validate_curriculum_manifest(bad)


class CurriculumSeedCommandTests(TestCase):
    """Test management command arguments, safety guards, planning, execution, and idempotency."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_superuser('seed-staff', 'staff@example.com', 'password')
        self.staff_profile = Profile.objects.create(user=self.staff)

        # Staff user without publish permission
        self.limited_staff = User.objects.create_user('seed-limited', 'limited@example.com', 'password', is_staff=True)
        self.limited_staff.user_permissions.add(
            Permission.objects.get(codename='add_roadmap', content_type__app_label='mentor'),
            Permission.objects.get(codename='add_roadmapnode', content_type__app_label='mentor'),
        )

        self.regular_user = User.objects.create_user('seed-regular', 'regular@example.com', 'password')

    def test_dry_run_default_no_writes(self):
        out = io.StringIO()
        call_command('seed_roadmap_curriculum', stdout=out)

        self.assertEqual(Roadmap.objects.count(), 0)
        self.assertEqual(RoadmapNode.objects.count(), 0)

    def test_invalid_json_manifest_fails_command_with_command_error(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json') as tmp:
            tmp.write("{ invalid json syntax")
            tmp.flush()
            with self.assertRaises(CommandError):
                call_command('seed_roadmap_curriculum', '--manifest', tmp.name)
        self.assertEqual(Roadmap.objects.count(), 0)

    def test_apply_without_isolated_dev_flag_fails(self):
        with self.assertRaises(CommandError):
            call_command('seed_roadmap_curriculum', '--apply', '--user', self.staff.username)
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=False)
    def test_apply_without_settings_marker_fails(self):
        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_apply_without_user_fails(self):
        with self.assertRaises(CommandError):
            call_command('seed_roadmap_curriculum', '--apply', '--isolated-dev')
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_apply_with_non_staff_user_fails(self):
        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.regular_user.username,
            )
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_apply_with_missing_permissions_fails(self):
        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.limited_staff.username,
            )
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_unsupported_database_alias_fails(self):
        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
                '--database',
                'secondary',
            )
        self.assertEqual(Roadmap.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_apply_creates_exact_tree_and_skeleton_nodes(self):
        manifest = load_curriculum_manifest()
        out = io.StringIO()
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
            stdout=out,
        )

        roadmap = Roadmap.objects.get(slug=ROADMAP_SLUG)
        self.assertEqual(roadmap.title, manifest['roadmap']['title'])
        self.assertEqual(roadmap.status, Publication.PUBLISHED)
        self.assertEqual(roadmap.visibility, Visibility.PUBLIC)
        self.assertIsNone(roadmap.organization_id)

        nodes = list(RoadmapNode.objects.filter(roadmap=roadmap).select_related('parent'))
        self.assertEqual(len(nodes), 216)
        nodes_by_slug = {n.slug: n for n in nodes}

        manifest_parent_map = {m['slug']: m['parent'] for m in manifest['nodes']}
        expected_ancestors = {}
        expected_levels = {}
        for m in manifest['nodes']:
            curr = m['slug']
            anc = []
            p = manifest_parent_map[curr]
            while p is not None:
                anc.append(p)
                p = manifest_parent_map[p]
            expected_ancestors[curr] = list(reversed(anc))
            expected_levels[curr] = len(anc)

        for m in manifest['nodes']:
            slug = m['slug']
            self.assertIn(slug, nodes_by_slug)
            node = nodes_by_slug[slug]

            self.assertEqual(node.title, m['title'])
            self.assertEqual(node.type, m['type'])
            self.assertEqual(node.difficulty, m['difficulty'])
            self.assertEqual(node.position, m['position'])
            self.assertEqual(node.status, Publication.PUBLISHED)
            self.assertIsNone(node.learning_topic_id)

            if m['parent'] is None:
                self.assertIsNone(node.parent_id)
            else:
                self.assertIsNotNone(node.parent_id)
                self.assertEqual(node.parent.slug, m['parent'])

            self.assertEqual(node.level, expected_levels[slug])
            actual_ancestors = list(node.get_ancestors().values_list('slug', flat=True))
            self.assertEqual(actual_ancestors, expected_ancestors[slug])

        # No fake content created in database
        self.assertEqual(LearningTopic.objects.count(), 0)
        self.assertEqual(TopicLesson.objects.count(), 0)
        self.assertEqual(NodeProblem.objects.count(), 0)
        self.assertEqual(RoadmapPrerequisite.objects.count(), 0)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_reapply_is_idempotent_no_revision_churn(self):
        # First apply
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
        )
        roadmap = Roadmap.objects.get(slug=ROADMAP_SLUG)
        rev_after_first = roadmap.tree_revision

        # Second apply (reapply)
        out = io.StringIO()
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
            stdout=out,
        )

        roadmap.refresh_from_db()
        self.assertEqual(roadmap.tree_revision, rev_after_first, "Reapply must cause zero revision churn")

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_reapply_preserves_attached_content_and_relationships(self):
        # Initial seed
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
        )
        roadmap = Roadmap.objects.get(slug=ROADMAP_SLUG)

        # Attach real LearningTopic to 'binary-search'
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        topic = LearningTopic.objects.create(
            name='Binary Search Theory',
            slug='binary-search-theory',
            introduction='Comprehensive guide to binary search.',
            status=Publication.PUBLISHED,
        )
        # Real TopicLesson draft with body
        lesson = TopicLesson.objects.create(
            topic=topic,
            title='Binary Invariants',
            slug='binary-invariants',
            position=0,
            body='Detailed text on monotonic search space and invariants.',
            status=Publication.DRAFT,
        )
        node.learning_topic = topic
        node.is_optional_review = True
        node.save()

        # Attach real Problem
        group = ProblemGroup.objects.create(name='rm-group', full_name='RM Group')
        prob = Problem.objects.create(
            code='BS01',
            name='Binary Search Problem 1',
            group=group,
            time_limit=1,
            memory_limit=65536,
            points=100,
            is_public=True,
        )
        link = save_problem_link(self.staff, NodeProblem(node=node, problem=prob))

        # Real RoadmapPrerequisite edge between curriculum nodes
        other_node = RoadmapNode.objects.get(roadmap=roadmap, slug='two-pointers')
        prereq_edge = RoadmapPrerequisite.objects.create(node=node, prerequisite=other_node)

        # Snapshot complete state before reapply
        roadmap.refresh_from_db()
        roadmap_snapshot = (roadmap.tree_revision, roadmap.title, roadmap.slug, roadmap.status, roadmap.visibility)
        nodes_snapshot = list(
            RoadmapNode.objects.filter(roadmap=roadmap).order_by('pk').values(
                'id', 'slug', 'title', 'type', 'difficulty', 'position', 'parent_id',
                'status', 'is_optional_review', 'learning_topic_id', 'lft', 'rght', 'tree_id', 'level'
            )
        )
        topic_snapshot = list(
            LearningTopic.objects.filter(pk=topic.pk).values(
                'id', 'name', 'slug', 'introduction', 'status', 'content_revision'
            )
        )
        lesson_snapshot = list(
            TopicLesson.objects.filter(pk=lesson.pk).values(
                'id', 'topic_id', 'title', 'slug', 'position', 'body', 'status', 'content_revision'
            )
        )
        links_snapshot = list(
            NodeProblem.objects.filter(pk=link.pk).values('id', 'node_id', 'problem_id', 'position')
        )
        prereqs_snapshot = list(
            RoadmapPrerequisite.objects.filter(pk=prereq_edge.pk).values('id', 'node_id', 'prerequisite_id')
        )

        # Reapply seed
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
        )

        # Assert identical afterward
        roadmap.refresh_from_db()
        self.assertEqual(
            (roadmap.tree_revision, roadmap.title, roadmap.slug, roadmap.status, roadmap.visibility),
            roadmap_snapshot,
        )
        after_nodes_snapshot = list(
            RoadmapNode.objects.filter(roadmap=roadmap).order_by('pk').values(
                'id', 'slug', 'title', 'type', 'difficulty', 'position', 'parent_id',
                'status', 'is_optional_review', 'learning_topic_id', 'lft', 'rght', 'tree_id', 'level'
            )
        )
        self.assertEqual(after_nodes_snapshot, nodes_snapshot)
        self.assertEqual(
            list(LearningTopic.objects.filter(pk=topic.pk).values(
                'id', 'name', 'slug', 'introduction', 'status', 'content_revision'
            )),
            topic_snapshot,
        )
        self.assertEqual(
            list(TopicLesson.objects.filter(pk=lesson.pk).values(
                'id', 'topic_id', 'title', 'slug', 'position', 'body', 'status', 'content_revision'
            )),
            lesson_snapshot,
        )
        self.assertEqual(
            list(NodeProblem.objects.filter(pk=link.pk).values('id', 'node_id', 'problem_id', 'position')),
            links_snapshot,
        )
        self.assertEqual(
            list(RoadmapPrerequisite.objects.filter(pk=prereq_edge.pk).values('id', 'node_id', 'prerequisite_id')),
            prereqs_snapshot,
        )


class CurriculumConflictDetectionTests(TestCase):
    """Test atomic failure and safe refusal on metadata, structural, or draft collisions."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_superuser('seed-conflict-staff', 'staff@example.com', 'password')
        self.staff_profile = Profile.objects.create(user=self.staff)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def _seed_initial(self):
        call_command(
            'seed_roadmap_curriculum',
            '--apply',
            '--isolated-dev',
            '--user',
            self.staff.username,
        )
        return Roadmap.objects.get(slug=ROADMAP_SLUG)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_title_mismatch_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        node.title = 'Tìm kiếm nhị phân đã đổi tên'
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.title, 'Tìm kiếm nhị phân đã đổi tên')
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_difficulty_mismatch_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        node.difficulty = RoadmapNode.Difficulty.ADVANCED
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.difficulty, RoadmapNode.Difficulty.ADVANCED)
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_type_mismatch_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        node.type = RoadmapNode.Type.GROUP
        node.difficulty = None
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.type, RoadmapNode.Type.GROUP)
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_parent_mismatch_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        other_parent = RoadmapNode.objects.get(roadmap=roadmap, slug='sorting')
        node.parent = other_parent
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.parent_id, other_parent.pk)
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_position_mismatch_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        node.position = 99
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.position, 99)
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_draft_collision_fails_atomically(self):
        roadmap = self._seed_initial()
        node = RoadmapNode.objects.get(roadmap=roadmap, slug='binary-search')
        node.status = Publication.DRAFT
        node.save()

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        node.refresh_from_db()
        self.assertEqual(node.status, Publication.DRAFT, "Draft status must not be auto-republished")
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 216)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_extra_unexpected_node_fails_atomically(self):
        roadmap = self._seed_initial()
        root = RoadmapNode.objects.get(roadmap=roadmap, slug='foundations')
        create_node(
            self.staff,
            roadmap=roadmap,
            parent=root,
            title='Custom Editorial Group',
            slug='custom-editorial-group',
            type=RoadmapNode.Type.GROUP,
            position=99,
            status=Publication.PUBLISHED,
        )

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        self.assertTrue(RoadmapNode.objects.filter(roadmap=roadmap, slug='custom-editorial-group').exists())
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 217)

    @override_settings(ROADMAP_CURRICULUM_SEED_ALLOWED=True)
    def test_container_scope_mismatch_fails_atomically(self):
        org = Organization.objects.create(name='Test Org', slug='test-org', short_name='TO', about='')
        Roadmap.objects.create(
            title='Lộ trình Competitive Programming',
            slug=ROADMAP_SLUG,
            visibility=Visibility.ORGANIZATION,
            organization=org,
            status=Publication.PUBLISHED,
        )

        with self.assertRaises(CommandError):
            call_command(
                'seed_roadmap_curriculum',
                '--apply',
                '--isolated-dev',
                '--user',
                self.staff.username,
            )
        roadmap = Roadmap.objects.get(slug=ROADMAP_SLUG)
        self.assertEqual(roadmap.visibility, Visibility.ORGANIZATION)
        self.assertEqual(RoadmapNode.objects.filter(roadmap=roadmap).count(), 0)

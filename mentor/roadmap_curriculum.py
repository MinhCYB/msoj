"""Curriculum manifest management, validation, planning, and safe seeding."""
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .roadmap_models import Publication, Roadmap, RoadmapNode, Visibility, lock_roadmap_forest
from .roadmap_services import save_content, save_node

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent / 'curriculum_v1.json'
ROADMAP_SLUG = 'competitive-programming'


class CurriculumValidationError(Exception):
    """Raised when curriculum manifest fails structural or semantic invariants."""


class CurriculumConflictError(Exception):
    """Raised when existing database state conflicts with manifest during seeding."""

    def __init__(self, conflicts: List['CurriculumConflict']):
        self.conflicts = conflicts
        messages = [c.message for c in conflicts]
        super().__init__(
            f"Curriculum seeding conflicts detected ({len(conflicts)}):\n"
            + "\n".join(f"- {m}" for m in messages)
        )


@dataclass
class CurriculumConflict:
    kind: str
    slug: str
    message: str
    existing_value: Any = None
    expected_value: Any = None


@dataclass
class CurriculumPlan:
    roadmap_slug: str
    roadmap_action: str  # 'create', 'match', or 'conflict'
    roadmap_title: str
    nodes_to_create: List[Dict[str, Any]] = field(default_factory=list)
    nodes_matched: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[CurriculumConflict] = field(default_factory=list)
    extra_nodes: List[str] = field(default_factory=list)
    prerequisite_targets_count: int = 69
    prerequisite_edges_count: int = 136

    @property
    def is_valid_for_apply(self) -> bool:
        return len(self.conflicts) == 0 and len(self.extra_nodes) == 0


def load_curriculum_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load curriculum manifest from machine-readable JSON. Never parses Markdown at runtime."""
    path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH

    if not path.is_file():
        raise FileNotFoundError(f"Curriculum manifest file not found: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as err:
        raise CurriculumValidationError(f"Invalid JSON in manifest file '{path}': {err}") from err


def validate_curriculum_manifest(manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate all structural, semantic, and relational invariants of the curriculum manifest.
    Malformed shapes or invalid fields strictly raise typed CurriculumValidationError.
    """
    if manifest is None:
        manifest = load_curriculum_manifest()

    if not isinstance(manifest, dict):
        raise CurriculumValidationError(f"Manifest root must be a dictionary, got {type(manifest).__name__}")

    if manifest.get('version') != '1':
        raise CurriculumValidationError(f"Expected manifest version '1', got '{manifest.get('version')}'")

    roadmap_data = manifest.get('roadmap')
    if not isinstance(roadmap_data, dict):
        raise CurriculumValidationError("Manifest missing 'roadmap' object")
    if roadmap_data.get('slug') != ROADMAP_SLUG:
        raise CurriculumValidationError(f"Expected roadmap slug '{ROADMAP_SLUG}', got '{roadmap_data.get('slug')}'")
    if not isinstance(roadmap_data.get('title'), str) or not roadmap_data.get('title'):
        raise CurriculumValidationError("Roadmap title must be a non-empty string")

    nodes = manifest.get('nodes')
    if not isinstance(nodes, list):
        raise CurriculumValidationError("Manifest missing 'nodes' list")
    if len(nodes) != 216:
        raise CurriculumValidationError(f"Expected exactly 216 nodes, found {len(nodes)}")

    slugs: List[str] = []
    seen_slugs: Set[str] = set()
    parent_map: Dict[str, Optional[str]] = {}
    children_by_parent: Dict[Optional[str], List[Dict[str, Any]]] = {}
    roots: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    topics: List[Dict[str, Any]] = []

    REQUIRED_NODE_KEYS = ('slug', 'title', 'parent', 'type', 'difficulty', 'position')
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise CurriculumValidationError(f"Node at index {idx} must be a dictionary, got {type(node).__name__}")

        for req_key in REQUIRED_NODE_KEYS:
            if req_key not in node:
                raise CurriculumValidationError(f"Node at index {idx} missing required key '{req_key}'")

        slug = node['slug']
        title = node['title']
        parent = node['parent']
        ntype = node['type']
        diff = node['difficulty']
        pos = node['position']

        if not isinstance(slug, str) or not slug or len(slug) > 100:
            raise CurriculumValidationError(f"Invalid slug for node at index {idx}: must be non-empty string <= 100 chars")
        if not isinstance(title, str) or not title or len(title) > 200:
            raise CurriculumValidationError(f"Invalid title for node '{slug}': must be non-empty string <= 200 chars")

        if parent is not None and not isinstance(parent, str):
            raise CurriculumValidationError(f"Parent of node '{slug}' must be a string slug or null")

        if not isinstance(pos, int) or isinstance(pos, bool):
            raise CurriculumValidationError(f"Position of node '{slug}' must be an integer, got {type(pos).__name__}")

        if ntype not in ('GROUP', 'TOPIC'):
            raise CurriculumValidationError(f"Invalid node type '{ntype}' for '{slug}'; expected GROUP or TOPIC")

        if ntype == 'GROUP':
            groups.append(node)
            if diff is not None:
                raise CurriculumValidationError(f"GROUP node '{slug}' must have null difficulty, got '{diff}'")
        else:
            topics.append(node)
            if diff not in ('BASIC', 'INTERMEDIATE', 'ADVANCED', None):
                raise CurriculumValidationError(f"Invalid difficulty '{diff}' for TOPIC '{slug}'")

        if parent is None:
            roots.append(node)

        slugs.append(slug)
        parent_map[slug] = parent
        children_by_parent.setdefault(parent, []).append(node)

    if len(groups) != 27:
        raise CurriculumValidationError(f"Expected exactly 27 GROUP nodes, found {len(groups)}")
    if len(topics) != 189:
        raise CurriculumValidationError(f"Expected exactly 189 TOPIC nodes, found {len(topics)}")
    if len(roots) != 13:
        raise CurriculumValidationError(f"Expected exactly 13 root nodes, found {len(roots)}")

    for r in roots:
        if r.get('type') != 'GROUP':
            raise CurriculumValidationError(f"Root node '{r.get('slug')}' must have type GROUP")

    root_positions = [r.get('position') for r in roots]
    if root_positions != list(range(13)):
        raise CurriculumValidationError(f"Root positions must be 0..12 consecutive, got {root_positions}")

    if len(slugs) != len(set(slugs)):
        raise CurriculumValidationError("Manifest contains duplicate node slugs")

    slug_set: Set[str] = set(slugs)

    # Validate parent topological order
    for node in nodes:
        slug = node['slug']
        parent = node['parent']
        if parent is not None:
            if parent not in slug_set:
                raise CurriculumValidationError(f"Parent '{parent}' of node '{slug}' does not exist in catalog")
            if parent not in seen_slugs:
                raise CurriculumValidationError(f"Parent '{parent}' must appear before child '{slug}' in manifest")
        seen_slugs.add(slug)

    # Validate sibling positions (0-based consecutive per parent)
    for p_slug, children in children_by_parent.items():
        positions = [c['position'] for c in children]
        expected = list(range(len(children)))
        if positions != expected:
            raise CurriculumValidationError(
                f"Sibling positions for parent '{p_slug}' must be 0-based consecutive: {positions}"
            )

    # Validate depth and tree acyclicity
    for slug in slugs:
        depth = 1
        curr = slug
        visited = {curr}
        while parent_map[curr] is not None:
            curr = parent_map[curr]
            if curr in visited:
                raise CurriculumValidationError(f"Cycle detected in parent hierarchy for '{slug}'")
            visited.add(curr)
            depth += 1
        if depth > 4:
            raise CurriculumValidationError(f"Node '{slug}' exceeds max depth 4 (depth: {depth})")

    # Validate prerequisite graph
    prereqs = manifest.get('prerequisites')
    if not isinstance(prereqs, dict):
        raise CurriculumValidationError("Manifest missing 'prerequisites' dictionary")

    prereq_edges = prereqs.get('edges')
    if not isinstance(prereq_edges, list):
        raise CurriculumValidationError("Manifest 'prerequisites.edges' must be a list")

    if len(prereq_edges) != 69:
        raise CurriculumValidationError(f"Expected exactly 69 prerequisite targets, found {len(prereq_edges)}")

    seen_targets: Set[str] = set()
    distinct_edges: Set[Tuple[str, str]] = set()
    node_by_slug = {n['slug']: n for n in nodes}
    in_degree: Dict[str, int] = {}
    adj: Dict[str, List[str]] = {}
    prereq_nodes: Set[str] = set()

    for idx, p in enumerate(prereq_edges):
        if not isinstance(p, dict):
            raise CurriculumValidationError(f"Prerequisite edge at index {idx} must be a dictionary")

        target = p.get('target')
        if not isinstance(target, str) or target not in node_by_slug:
            raise CurriculumValidationError(f"Prerequisite target '{target}' does not exist in catalog")
        if node_by_slug[target]['type'] != 'TOPIC':
            raise CurriculumValidationError(f"Prerequisite target '{target}' must be a TOPIC node")
        if target in seen_targets:
            raise CurriculumValidationError(f"Duplicate prerequisite target '{target}'")
        seen_targets.add(target)

        priors = p.get('prerequisites')
        if not isinstance(priors, list) or not priors:
            raise CurriculumValidationError(f"Prerequisite target '{target}' must have a non-empty list of priors")

        prereq_nodes.add(target)
        seen_priors_for_target: Set[str] = set()
        for prior in priors:
            if not isinstance(prior, str) or prior not in node_by_slug:
                raise CurriculumValidationError(f"Prerequisite prior '{prior}' does not exist in catalog")
            if node_by_slug[prior]['type'] != 'TOPIC':
                raise CurriculumValidationError(f"Prerequisite prior '{prior}' must be a TOPIC node")
            if prior in seen_priors_for_target:
                raise CurriculumValidationError(f"Duplicate prior '{prior}' for target '{target}'")
            seen_priors_for_target.add(prior)

            edge_pair = (prior, target)
            if edge_pair in distinct_edges:
                raise CurriculumValidationError(f"Duplicate prerequisite edge {edge_pair}")
            distinct_edges.add(edge_pair)

            adj.setdefault(prior, []).append(target)
            in_degree[target] = in_degree.get(target, 0) + 1
            prereq_nodes.add(prior)

    if len(seen_targets) != 69:
        raise CurriculumValidationError(f"Expected exactly 69 distinct prerequisite targets, found {len(seen_targets)}")
    if len(distinct_edges) != 136:
        raise CurriculumValidationError(f"Expected exactly 136 distinct prerequisite edges, found {len(distinct_edges)}")

    # Check prerequisite acyclic DAG via Kahn's algorithm
    queue = [n for n in prereq_nodes if in_degree.get(n, 0) == 0]
    visited_count = 0
    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for nxt in adj.get(curr, []):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if visited_count != len(prereq_nodes):
        raise CurriculumValidationError("Prerequisite graph contains a cycle")

    # Validate crosswalk slug integrity
    if 'crosswalk' in manifest:
        crosswalk = manifest['crosswalk']
        if crosswalk is not None:
            if not isinstance(crosswalk, dict):
                raise CurriculumValidationError("Manifest 'crosswalk' must be a dictionary")

            for coll_name in ('r_topics', 'w_topics', 'g_links', 'm_supplements', 'r_groups', 'g_headings'):
                if coll_name in crosswalk:
                    coll = crosswalk[coll_name]
                    if not isinstance(coll, list):
                        raise CurriculumValidationError(f"Crosswalk '{coll_name}' must be a list")

            for rt in crosswalk.get('r_topics') or []:
                if not isinstance(rt, dict):
                    raise CurriculumValidationError("Crosswalk R topic entry must be a dictionary")
                slugs_val = rt.get('slugs')
                if slugs_val is None:
                    slug_single = rt.get('slug')
                    if slug_single is None:
                        slugs_to_check = []
                    elif isinstance(slug_single, str):
                        slugs_to_check = [slug_single]
                    else:
                        raise CurriculumValidationError("Crosswalk R topic 'slug' must be a string")
                elif isinstance(slugs_val, list):
                    slugs_to_check = slugs_val
                else:
                    raise CurriculumValidationError("Crosswalk R topic 'slugs' must be a list")
                for s in slugs_to_check:
                    if not isinstance(s, str):
                        raise CurriculumValidationError(f"Crosswalk R topic slug must be a string, got {type(s).__name__}")
                    if s not in slug_set:
                        raise CurriculumValidationError(f"Crosswalk R topic refers to unknown slug '{s}'")

            for wt in crosswalk.get('w_topics') or []:
                if not isinstance(wt, dict):
                    raise CurriculumValidationError("Crosswalk W topic entry must be a dictionary")
                slugs_val = wt.get('slugs')
                if not isinstance(slugs_val, list):
                    raise CurriculumValidationError("Crosswalk W topic 'slugs' must be a list")
                for s in slugs_val:
                    if not isinstance(s, str):
                        raise CurriculumValidationError(f"Crosswalk W topic slug must be a string, got {type(s).__name__}")
                    if s not in slug_set:
                        raise CurriculumValidationError(f"Crosswalk W topic refers to unknown slug '{s}'")

            for gl in crosswalk.get('g_links') or []:
                if not isinstance(gl, dict):
                    raise CurriculumValidationError("Crosswalk G link entry must be a dictionary")
                slugs_val = gl.get('slugs')
                if not isinstance(slugs_val, list):
                    raise CurriculumValidationError("Crosswalk G link 'slugs' must be a list")
                for s in slugs_val:
                    if not isinstance(s, str):
                        raise CurriculumValidationError(f"Crosswalk G link slug must be a string, got {type(s).__name__}")
                    if s not in slug_set:
                        raise CurriculumValidationError(f"Crosswalk G link refers to unknown slug '{s}'")

            for ms in crosswalk.get('m_supplements') or []:
                if not isinstance(ms, dict):
                    raise CurriculumValidationError("Crosswalk M supplement entry must be a dictionary")
                s = ms.get('slug')
                if not isinstance(s, str):
                    raise CurriculumValidationError(f"Crosswalk M supplement slug must be a string, got {type(s).__name__}")
                if s not in slug_set:
                    raise CurriculumValidationError(f"Crosswalk M supplement refers to unknown slug '{s}'")
    return manifest


def plan_curriculum_seed(
    manifest: Optional[Dict[str, Any]] = None,
    database: str = 'default',
) -> CurriculumPlan:
    """
    Inspect database under transaction and forest lock and compare against manifest.
    Returns a CurriculumPlan detailing planned additions, exact matches, conflicts, and extra nodes.
    Supports only 'default' database. Never writes to database.
    """
    if database != 'default':
        raise ValueError(
            f"Unsupported database '{database}'. Roadmap services and lock_roadmap_forest "
            "are only safe on the 'default' database."
        )

    if manifest is None:
        manifest = load_curriculum_manifest()
    validate_curriculum_manifest(manifest)

    roadmap_data = manifest['roadmap']
    expected_title = roadmap_data['title']
    expected_slug = ROADMAP_SLUG

    conflicts: List[CurriculumConflict] = []
    nodes_to_create: List[Dict[str, Any]] = []
    nodes_matched: List[Dict[str, Any]] = []
    extra_nodes: List[str] = []

    with transaction.atomic(using=database):
        lock_roadmap_forest()

        existing_roadmap = Roadmap.objects.using(database).filter(slug=expected_slug).first()

        if existing_roadmap is None:
            roadmap_action = 'create'
            for node in manifest['nodes']:
                nodes_to_create.append(node)
            return CurriculumPlan(
                roadmap_slug=expected_slug,
                roadmap_action=roadmap_action,
                roadmap_title=expected_title,
                nodes_to_create=nodes_to_create,
                nodes_matched=nodes_matched,
                conflicts=conflicts,
                extra_nodes=extra_nodes,
                prerequisite_targets_count=len(manifest.get('prerequisites', {}).get('edges', [])),
                prerequisite_edges_count=manifest.get('summary', {}).get('prerequisite_edges_count', 136),
            )

        roadmap_action = 'match'

        # Check container fields
        if existing_roadmap.visibility != Visibility.PUBLIC:
            conflicts.append(CurriculumConflict(
                kind='container_scope_mismatch',
                slug=expected_slug,
                message=f"Roadmap '{expected_slug}' visibility is '{existing_roadmap.visibility}'; expected PUBLIC.",
                existing_value=existing_roadmap.visibility,
                expected_value=Visibility.PUBLIC,
            ))
        if existing_roadmap.organization_id is not None:
            conflicts.append(CurriculumConflict(
                kind='container_scope_mismatch',
                slug=expected_slug,
                message=f"Roadmap '{expected_slug}' is bound to organization {existing_roadmap.organization_id}; expected null.",
                existing_value=existing_roadmap.organization_id,
                expected_value=None,
            ))
        if existing_roadmap.title != expected_title:
            conflicts.append(CurriculumConflict(
                kind='container_title_mismatch',
                slug=expected_slug,
                message=f"Roadmap '{expected_slug}' title is '{existing_roadmap.title}'; expected '{expected_title}'.",
                existing_value=existing_roadmap.title,
                expected_value=expected_title,
            ))
        if existing_roadmap.status != Publication.PUBLISHED:
            conflicts.append(CurriculumConflict(
                kind='container_status_mismatch',
                slug=expected_slug,
                message=f"Roadmap '{expected_slug}' status is '{existing_roadmap.status}'; expected PUBLISHED.",
                existing_value=existing_roadmap.status,
                expected_value=Publication.PUBLISHED,
            ))

        existing_nodes_qs = RoadmapNode.objects.using(database).filter(roadmap=existing_roadmap).select_related('parent')
        existing_by_slug: Dict[str, RoadmapNode] = {n.slug: n for n in existing_nodes_qs}

        manifest_slugs = {n['slug'] for n in manifest['nodes']}
        for extra_slug in sorted(set(existing_by_slug.keys()) - manifest_slugs):
            extra_nodes.append(extra_slug)
            conflicts.append(CurriculumConflict(
                kind='extra_node',
                slug=extra_slug,
                message=f"Unexpected extra node '{extra_slug}' exists in roadmap '{expected_slug}'.",
                existing_value=extra_slug,
                expected_value=None,
            ))

        for node_data in manifest['nodes']:
            slug = node_data['slug']
            if slug not in existing_by_slug:
                nodes_to_create.append(node_data)
                continue

            existing = existing_by_slug[slug]
            has_node_conflict = False

            if existing.title != node_data['title']:
                conflicts.append(CurriculumConflict(
                    kind='title_mismatch',
                    slug=slug,
                    message=f"Node '{slug}' title mismatch: existing='{existing.title}', expected='{node_data['title']}'.",
                    existing_value=existing.title,
                    expected_value=node_data['title'],
                ))
                has_node_conflict = True

            if existing.type != node_data['type']:
                conflicts.append(CurriculumConflict(
                    kind='type_mismatch',
                    slug=slug,
                    message=f"Node '{slug}' type mismatch: existing='{existing.type}', expected='{node_data['type']}'.",
                    existing_value=existing.type,
                    expected_value=node_data['type'],
                ))
                has_node_conflict = True

            if existing.difficulty != node_data['difficulty']:
                conflicts.append(CurriculumConflict(
                    kind='difficulty_mismatch',
                    slug=slug,
                    message=f"Node '{slug}' difficulty mismatch: existing='{existing.difficulty}', expected='{node_data['difficulty']}'.",
                    existing_value=existing.difficulty,
                    expected_value=node_data['difficulty'],
                ))
                has_node_conflict = True

            existing_parent_slug = existing.parent.slug if existing.parent else None
            expected_parent_slug = node_data['parent']
            if existing_parent_slug != expected_parent_slug:
                conflicts.append(CurriculumConflict(
                    kind='parent_mismatch',
                    slug=slug,
                    message=f"Node '{slug}' parent mismatch: existing='{existing_parent_slug}', expected='{expected_parent_slug}'.",
                    existing_value=existing_parent_slug,
                    expected_value=expected_parent_slug,
                ))
                has_node_conflict = True

            if existing.position != node_data['position']:
                conflicts.append(CurriculumConflict(
                    kind='position_mismatch',
                    slug=slug,
                    message=f"Node '{slug}' position mismatch: existing={existing.position}, expected={node_data['position']}.",
                    existing_value=existing.position,
                    expected_value=node_data['position'],
                ))
                has_node_conflict = True

            # Avoid auto-republishing draft nodes
            if existing.status != Publication.PUBLISHED:
                conflicts.append(CurriculumConflict(
                    kind='draft_collision',
                    slug=slug,
                    message=f"Node '{slug}' is DRAFT in database; auto-republishing draft nodes is forbidden.",
                    existing_value=existing.status,
                    expected_value=Publication.PUBLISHED,
                ))
                has_node_conflict = True

            if not has_node_conflict:
                nodes_matched.append(node_data)

        if conflicts and roadmap_action != 'create':
            roadmap_action = 'conflict'

        return CurriculumPlan(
            roadmap_slug=expected_slug,
            roadmap_action=roadmap_action,
            roadmap_title=expected_title,
            nodes_to_create=nodes_to_create,
            nodes_matched=nodes_matched,
            conflicts=conflicts,
            extra_nodes=extra_nodes,
            prerequisite_targets_count=len(manifest.get('prerequisites', {}).get('edges', [])),
            prerequisite_edges_count=manifest.get('summary', {}).get('prerequisite_edges_count', 136),
        )


@transaction.atomic
def apply_curriculum_seed(
    user: Any,
    manifest: Optional[Dict[str, Any]] = None,
    database: str = 'default',
    isolated_dev: bool = False,
) -> Dict[str, Any]:
    """
    Atomically apply curriculum manifest into the database using existing services.
    Requires:
    - database == 'default'
    - getattr(settings, 'ROADMAP_CURRICULUM_SEED_ALLOWED', False) is True
    - isolated_dev is True
    - user is active staff with mentor.add_roadmap, mentor.add_roadmapnode, mentor.publish_roadmap
    - Zero structural, title, difficulty, publication, or extra node conflicts

    Existing matching nodes are no-ops: attached LearningTopic, NodeProblem, prerequisites,
    and admin content are strictly preserved with zero revision churn.
    Prerequisites and source metadata remain manifest-only per policy.
    """
    if database != 'default':
        raise ValueError(
            f"Unsupported database '{database}'. Roadmap services and lock_roadmap_forest "
            "are only safe on the 'default' database."
        )

    if not getattr(settings, 'ROADMAP_CURRICULUM_SEED_ALLOWED', False):
        raise PermissionDenied(
            "Curriculum seeding is forbidden: settings.ROADMAP_CURRICULUM_SEED_ALLOWED is False. "
            "Seeding is strictly limited to isolated development or testing environments."
        )

    if not isolated_dev:
        raise PermissionDenied(
            "Curriculum seeding requires explicit --isolated-dev opt-in flag."
        )

    if not user.is_active or not user.is_staff:
        raise PermissionDenied("Curriculum seeding requires an active staff user.")

    required_permissions = ['mentor.add_roadmap', 'mentor.add_roadmapnode', 'mentor.publish_roadmap']
    missing_permissions = [perm for perm in required_permissions if not user.has_perm(perm)]
    if missing_permissions:
        raise PermissionDenied(
            f"User '{user.username}' lacks required permissions for seeding: {', '.join(missing_permissions)}"
        )

    if manifest is None:
        manifest = load_curriculum_manifest()
    validate_curriculum_manifest(manifest)

    lock_roadmap_forest()

    plan = plan_curriculum_seed(manifest=manifest, database=database)

    if not plan.is_valid_for_apply:
        raise CurriculumConflictError(plan.conflicts)

    roadmap_data = manifest['roadmap']
    created_roadmap = False

    if plan.roadmap_action == 'create':
        roadmap = Roadmap(
            slug=roadmap_data['slug'],
            title=roadmap_data['title'],
            introduction=roadmap_data.get('introduction', ''),
            status=Publication.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        save_content(user, roadmap)
        created_roadmap = True
    else:
        roadmap = Roadmap.objects.using(database).get(slug=roadmap_data['slug'])

    created_nodes_count = 0
    if plan.nodes_to_create:
        nodes_by_slug: Dict[str, RoadmapNode] = {
            n.slug: n for n in RoadmapNode.objects.using(database).filter(roadmap=roadmap)
        }

        for node_data in plan.nodes_to_create:
            parent_node = None
            parent_slug = node_data.get('parent')
            if parent_slug:
                parent_node = nodes_by_slug[parent_slug]

            node = RoadmapNode(
                roadmap=roadmap,
                parent=parent_node,
                title=node_data['title'],
                slug=node_data['slug'],
                type=node_data['type'],
                position=node_data['position'],
                difficulty=node_data['difficulty'],
                status=Publication.PUBLISHED,
                learning_topic=None,
            )
            save_node(user, node)
            nodes_by_slug[node.slug] = node
            created_nodes_count += 1

    return {
        'roadmap_slug': roadmap.slug,
        'roadmap_created': created_roadmap,
        'nodes_created': created_nodes_count,
        'nodes_matched': len(plan.nodes_matched),
        'prerequisite_targets_count': plan.prerequisite_targets_count,
        'prerequisite_edges_count': plan.prerequisite_edges_count,
        'conflicts_count': 0,
    }

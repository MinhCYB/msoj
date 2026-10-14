"""Bounded-query read selectors for Mentor Roadmap v2 Phase 1.

Implements read selectors with batch access evaluation, MPTT subtree
aggregation, signed keyset cursors, and Submission.result='AC' parity.
"""
from django.contrib.auth.models import AnonymousUser
from django.core import signing
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from judge.models import ContestProblem, Problem, Submission

from .roadmap_icons import resolve_node_icon
from .roadmap_models import (
    LearningTopic,
    NodeProblem,
    Publication,
    Roadmap,
    RoadmapNode,
    TopicLesson,
    TopicLessonQAMessage,
    TopicLessonState,
    Visibility,
)

CURSOR_SALT = 'mentor.roadmap.cursor.v1'
CONTENT_STATE_AVAILABLE = 'AVAILABLE'
CONTENT_STATE_UPCOMING = 'UPCOMING'



class TreeRevisionStale(Exception):
    """Raised when a cursor's tree revision does not match the roadmap's revision."""
    def __init__(self, current_revision):
        self.current_revision = current_revision
        super().__init__(f'Tree revision is stale; expected {current_revision}')


def make_cursor(roadmap_id, parent_id, tree_revision, position, pk):
    return signing.dumps(
        {'r': roadmap_id, 'p': parent_id, 'v': tree_revision, 'pos': position, 'pk': pk},
        salt=CURSOR_SALT,
    )


def parse_cursor(cursor_str, roadmap_id, parent_id, tree_revision):
    try:
        data = signing.loads(cursor_str, salt=CURSOR_SALT)
    except Exception as e:
        raise ValueError('Invalid cursor format or signature') from e

    if not isinstance(data, dict):
        raise ValueError('Invalid cursor payload')

    if data.get('r') != roadmap_id or data.get('p') != parent_id:
        raise ValueError('Cursor is bound to a different roadmap or parent node')

    if data.get('v') != tree_revision:
        raise TreeRevisionStale(current_revision=tree_revision)

    pos, pk = data.get('pos'), data.get('pk')
    if not isinstance(pos, int) or not isinstance(pk, int):
        raise ValueError('Invalid cursor position or primary key')

    return pos, pk


def is_content_scoped_to_user(content, user):
    if user is None:
        user = AnonymousUser()
    if content.status != Publication.PUBLISHED:
        return False
    if content.visibility == Visibility.PUBLIC:
        return True
    if content.visibility == Visibility.ORGANIZATION:
        if not user.is_authenticated:
            return False
        profile = getattr(user, 'profile', None)
        if profile is None or not content.organization_id:
            return False
        return profile.organizations.filter(id=content.organization_id).exists()
    return False


def get_accessible_roadmaps(user):
    qs = Roadmap.objects.filter(status=Publication.PUBLISHED)
    if user is None or not user.is_authenticated:
        return qs.filter(visibility=Visibility.PUBLIC)
    profile = getattr(user, 'profile', None)
    if profile is None:
        return qs.filter(visibility=Visibility.PUBLIC)
    org_ids = profile.organizations.values_list('id', flat=True)
    return qs.filter(
        Q(visibility=Visibility.PUBLIC) |
        Q(visibility=Visibility.ORGANIZATION, organization__in=org_ids)
    )


def get_accessible_roadmap(user, slug):
    roadmap = Roadmap.objects.filter(slug=slug, status=Publication.PUBLISHED).first()
    if roadmap is None or not is_content_scoped_to_user(roadmap, user):
        return None
    return roadmap


def get_effective_published_nodes_filter(roadmap):
    draft_intervals = list(
        RoadmapNode.objects.filter(roadmap=roadmap, status=Publication.DRAFT)
        .values_list('tree_id', 'lft', 'rght')
    )
    if not draft_intervals:
        return Q(status=Publication.PUBLISHED)

    draft_intervals.sort(key=lambda x: (x[0], x[1], -x[2]))
    top_intervals = []
    current_tree_id, current_rght = None, -1
    for t_id, lft, rght in draft_intervals:
        if t_id != current_tree_id or lft > current_rght:
            top_intervals.append((t_id, lft, rght))
            current_tree_id, current_rght = t_id, rght

    exclude_q = Q(status=Publication.DRAFT)
    for t_id, lft, rght in top_intervals:
        exclude_q |= Q(tree_id=t_id, lft__gt=lft, rght__lt=rght)

    return Q(status=Publication.PUBLISHED) & ~exclude_q


def is_node_effective_published(roadmap, node):
    if node.roadmap_id != roadmap.id:
        return False
    if node.status != Publication.PUBLISHED:
        return False
    if node.parent_id is None:
        return True
    return not node.get_ancestors().filter(status=Publication.DRAFT).exists()


def get_effective_published_node(roadmap, node_id):
    node = RoadmapNode.objects.filter(roadmap=roadmap, pk=node_id).first()
    if node is None or not is_node_effective_published(roadmap, node):
        return None
    return node


def get_accessible_problem_ids(user, candidate_problem_ids):
    """
    Batch-evaluated object-level access adapter for candidate problems.
    Intersects Problem.get_visible_problems with an object-access Q adapter
    mirroring Problem.is_accessible_by without per-problem N+1 queries.
    """
    if not candidate_problem_ids:
        return set()

    if user is None:
        user = AnonymousUser()

    # Step 1: Base visible problems (enforces available/undeleted)
    base_qs = Problem.get_visible_problems(user).filter(id__in=candidate_problem_ids)

    # Step 2: Unauthenticated access
    if not user.is_authenticated:
        return set(base_qs.filter(is_public=True, is_organization_private=False).values_list('id', flat=True))

    profile = getattr(user, 'profile', None)
    if profile is None:
        return set()

    # Step 3: Current contest checks
    current_participation = getattr(profile, 'current_contest', None)
    contest_granted_pids = set()
    if current_participation is not None:
        if not current_participation.contest.can_join:
            # Prejoin contest suppression: blocks access to all problems
            return set()

        contest_granted_pids = set(
            ContestProblem.objects.filter(
                problem_id__in=candidate_problem_ids,
                contest__users__id=current_participation.id,
            ).values_list('problem_id', flat=True)
        )

    # Step 4: see_private_problem or (edit_own and edit_all) early all candidates
    edit_own = user.has_perm('judge.edit_own_problem')
    edit_all = edit_own and user.has_perm('judge.edit_all_problem')
    if user.has_perm('judge.see_private_problem') or edit_all:
        return set(base_qs.values_list('id', flat=True))

    # Step 5: Object-access Q differences
    user_org_ids = profile.organizations.values_list('id', flat=True)

    # public nonorg OR public-org membership/seeorg
    public_q = Q(is_public=True, is_organization_private=False)
    if user.has_perm('judge.see_organization_problem'):
        public_q |= Q(is_public=True, is_organization_private=True)
    else:
        public_q |= Q(is_public=True, is_organization_private=True, organization__in=user_org_ids)

    # roles (author, curator, tester across all statuses)
    roles_q = Problem.q_add_author_curator_tester(Q(), profile)

    # edit_own AND edit_public -> all public problems (including org-private)
    edit_public_q = Q(is_public=True) if (edit_own and user.has_perm('judge.edit_public_problem')) else Q(pk__in=[])

    accessible_pids = set(base_qs.filter(public_q | roles_q | edit_public_q).values_list('id', flat=True))

    if contest_granted_pids:
        accessible_pids |= set(base_qs.filter(id__in=contest_granted_pids).values_list('id', flat=True))

    return accessible_pids


def get_user_solved_problem_ids(user, accessible_problem_ids):
    if user is None or not user.is_authenticated or not accessible_problem_ids:
        return set()
    profile = getattr(user, 'profile', None)
    if profile is None:
        return set()
    return set(
        Submission.objects.filter(
            user=profile,
            result='AC',
            problem_id__in=accessible_problem_ids,
        ).values_list('problem_id', flat=True).distinct()
    )


def _format_progress_dict(problem_ids, solved_problem_ids, user, is_suppressed, scope='direct'):
    total = len(problem_ids)
    if is_suppressed:
        return {'state': 'unavailable', 'scope': scope, 'solved': None, 'total': 0}
    if user is None or not user.is_authenticated:
        return {'state': 'anonymous', 'scope': scope, 'solved': None, 'total': total}
    if total == 0:
        return {'state': 'empty', 'scope': scope, 'solved': 0, 'total': 0}
    return {'state': 'available', 'scope': scope, 'solved': len(problem_ids & solved_problem_ids), 'total': total}


class RoadmapSnapshot:
    """
    In-memory snapshot of effective-published tree and AC progress for a roadmap.
    Exposes:
    - snapshot.nodes: list of effective-published RoadmapNode instances
    - snapshot.progress(node, scope='direct'|'subtree'): dict with state, scope, solved, total
    - snapshot.overall_progress: dict with subtree progress for the entire roadmap
    """
    def __init__(self, user, roadmap):
        if user is None:
            user = AnonymousUser()
        self.user = user

        if isinstance(roadmap, (int, str)):
            lookup = {'slug': roadmap} if isinstance(roadmap, str) else {'pk': roadmap}
            roadmap = Roadmap.objects.filter(**lookup).first()
        elif roadmap is not None and getattr(roadmap, 'pk', None):
            roadmap = Roadmap.objects.filter(pk=roadmap.pk).first()

        self.roadmap = roadmap
        self.accessible = (
            roadmap is not None
            and is_content_scoped_to_user(roadmap, user)
        )

        if not self.accessible:
            self.nodes = []
            self.node_dict = {}
            self._direct_pids = {}
            self._subtree_pids = {}
            self._all_roadmap_pids = set()
            self._accessible_pids = set()
            self._solved_pids = set()
            self._is_suppressed = False
            return

        effective_filter = get_effective_published_nodes_filter(roadmap)
        self.nodes = list(
            RoadmapNode.objects.filter(roadmap=roadmap)
            .filter(effective_filter)
            .annotate(
                has_children=Exists(
                    RoadmapNode.objects.filter(parent=OuterRef('pk'), status=Publication.PUBLISHED)
                )
            )
            .select_related('learning_topic')
            .order_by('tree_id', 'lft')
        )
        self.node_dict = {node.id: node for node in self.nodes}

        all_links = list(
            NodeProblem.objects.filter(node__in=self.nodes).values_list('node_id', 'problem_id')
        )

        candidate_pids = set(row[1] for row in all_links)
        self._accessible_pids = get_accessible_problem_ids(user, candidate_pids)
        self._solved_pids = get_user_solved_problem_ids(user, self._accessible_pids)

        self._is_suppressed = False
        if user.is_authenticated:
            profile = getattr(user, 'profile', None)
            if profile is not None:
                c = getattr(profile, 'current_contest', None)
                if c is not None and not c.contest.can_join:
                    self._is_suppressed = True

        # Build direct map once
        self._direct_pids = {node.id: set() for node in self.nodes}
        for node_id, problem_id in all_links:
            if problem_id in self._accessible_pids and node_id in self._direct_pids:
                self._direct_pids[node_id].add(problem_id)

        # Build subtree sets via reversed preorder child->parent union
        self._subtree_pids = {node.id: set(self._direct_pids[node.id]) for node in self.nodes}
        for node in reversed(self.nodes):
            if node.parent_id and node.parent_id in self._subtree_pids:
                self._subtree_pids[node.parent_id].update(self._subtree_pids[node.id])

        self._all_roadmap_pids = candidate_pids & self._accessible_pids

    def __bool__(self):
        return self.accessible

    def _resolve_node_id(self, node):
        if node is None:
            return None
        if isinstance(node, int):
            return node
        if hasattr(node, 'id'):
            return node.id
        if hasattr(node, 'pk'):
            return node.pk
        if isinstance(node, dict) and 'id' in node:
            return node['id']
        return getattr(node, 'id', None)

    def progress(self, node=None, scope='direct'):
        node_id = self._resolve_node_id(node)
        if node_id is None:
            pids = self._all_roadmap_pids
            effective_scope = 'subtree'
        elif scope == 'direct':
            pids = self._direct_pids.get(node_id, set())
            effective_scope = 'direct'
        else:
            pids = self._subtree_pids.get(node_id, set())
            effective_scope = 'subtree'

        return _format_progress_dict(
            pids, self._solved_pids, self.user, self._is_suppressed, scope=effective_scope
        )

    @property
    def overall_progress(self):
        return self.progress(None, 'subtree')


def is_topic_accessible(topic, user):
    if topic is None or topic.status != Publication.PUBLISHED:
        return False
    return is_content_scoped_to_user(topic, user)

def _evaluate_readiness_state(roadmap, node_id, has_intro, has_lessons, has_exercises):
    is_ready = bool(has_intro or has_lessons or has_exercises)
    content_state = CONTENT_STATE_AVAILABLE if is_ready else CONTENT_STATE_UPCOMING
    learn_url = reverse('roadmap_node_learn', args=[roadmap.slug, node_id]) if is_ready else None
    return content_state, learn_url


def get_node_readiness(roadmap, node, user):
    """
    Evaluate content readiness for a single node.
    Returns (content_state, learn_url).
    """
    if user is None:
        user = AnonymousUser()

    topic = node.learning_topic
    topic_allowed = is_topic_accessible(topic, user)
    has_intro = bool(topic_allowed and topic and topic.introduction and topic.introduction.strip())

    has_lessons = False
    if topic_allowed and topic:
        has_lessons = any(
            bool(body and body.strip())
            for body in topic.lessons.filter(status=Publication.PUBLISHED).values_list('body', flat=True)
        )

    candidate_pids = set(node.problem_links.values_list('problem_id', flat=True))
    accessible_pids = get_accessible_problem_ids(user, candidate_pids)
    has_exercises = bool(accessible_pids)

    return _evaluate_readiness_state(roadmap, node.id, has_intro, has_lessons, has_exercises)

def serialize_node_list(roadmap, nodes, user):
    if not nodes:
        return []

    if user is None:
        user = AnonymousUser()

    snapshot = RoadmapSnapshot(user, roadmap)
    profile = getattr(user, 'profile', None) if user.is_authenticated else None
    user_org_ids = set(profile.organizations.values_list('id', flat=True)) if profile else set()

    def is_topic_allowed(topic):
        if topic is None or topic.status != Publication.PUBLISHED:
            return False
        if topic.visibility == Visibility.PUBLIC:
            return True
        if topic.visibility == Visibility.ORGANIZATION:
            return user.is_authenticated and bool(topic.organization_id and topic.organization_id in user_org_ids)
        return False

    missing_topic_node_ids = [
        node.id for node in nodes
        if node.learning_topic_id and 'learning_topic' not in getattr(node._state, 'fields_cache', {})
    ]
    if missing_topic_node_ids:
        topic_ids = {node.learning_topic_id for node in nodes if node.learning_topic_id}
        topic_map = {t.id: t for t in LearningTopic.objects.filter(id__in=topic_ids)}
        for node in nodes:
            if node.learning_topic_id and node.learning_topic_id in topic_map:
                node._state.fields_cache['learning_topic'] = topic_map[node.learning_topic_id]

    allowed_topic_ids = set()
    topics_with_intro = set()
    for node in nodes:
        topic = getattr(node, 'learning_topic', None)
        if topic and is_topic_allowed(topic):
            allowed_topic_ids.add(topic.id)
            if topic.introduction and topic.introduction.strip():
                topics_with_intro.add(topic.id)

    topics_with_lessons = set()
    if allowed_topic_ids:
        for tid, body in TopicLesson.objects.filter(
            topic_id__in=allowed_topic_ids,
            status=Publication.PUBLISHED,
        ).exclude(body='').values_list('topic_id', 'body'):
            if body.strip():
                topics_with_lessons.add(tid)

    serialized = []
    for node in nodes:
        direct_progress = snapshot.progress(node.id, 'direct')
        subtree_progress = snapshot.progress(node.id, 'subtree')

        topic = getattr(node, 'learning_topic', None)
        has_intro = bool(topic and topic.id in topics_with_intro)
        has_lessons = bool(topic and topic.id in topics_with_lessons)
        has_exercises = bool(snapshot._direct_pids.get(node.id))

        content_state, learn_url = _evaluate_readiness_state(
            roadmap, node.id, has_intro, has_lessons, has_exercises
        )
        focus_url = f"{reverse('roadmap_detail', args=[roadmap.slug])}?focus={node.id}"

        serialized.append({
            'id': node.id,
            'parent_id': node.parent_id,
            'type': node.type,
            'title': node.title,
            'slug': node.slug,
            'icon_class': resolve_node_icon(node.icon, node.slug, node.type),
            'depth': node.level,
            'position': node.position,
            'difficulty': node.difficulty,
            'has_children': bool(node.has_children),
            'content_state': content_state,
            'learn_url': learn_url,
            'focus_url': focus_url,
            'progress': direct_progress,
            'subtree_progress': subtree_progress,
        })

    return serialized


def get_roadmap_roots(roadmap, user, cursor_str=None, limit=50):
    if cursor_str:
        pos, pk = parse_cursor(cursor_str, roadmap.id, None, roadmap.tree_revision)
        keyset_filter = Q(position__gt=pos) | Q(position=pos, pk__gt=pk)
    else:
        keyset_filter = Q()

    roots_qs = (
        RoadmapNode.objects.filter(
            roadmap=roadmap,
            parent__isnull=True,
            status=Publication.PUBLISHED,
        )
        .filter(keyset_filter)
        .annotate(
            has_children=Exists(
                RoadmapNode.objects.filter(parent=OuterRef('pk'), status=Publication.PUBLISHED)
            )
        )
        .select_related('learning_topic')
        .order_by('position', 'pk')
    )

    fetch_limit = min(max(1, limit), 100)
    items = list(roots_qs[:fetch_limit + 1])
    has_next = len(items) > fetch_limit
    if has_next:
        items = items[:fetch_limit]
        last_item = items[-1]
        next_cursor = make_cursor(
            roadmap.id, None, roadmap.tree_revision, last_item.position, last_item.pk
        )
    else:
        next_cursor = None

    return serialize_node_list(roadmap, items, user), next_cursor


def get_node_immediate_children(roadmap, parent, user, cursor_str=None, limit=50):
    if cursor_str:
        pos, pk = parse_cursor(cursor_str, roadmap.id, parent.id, roadmap.tree_revision)
        keyset_filter = Q(position__gt=pos) | Q(position=pos, pk__gt=pk)
    else:
        keyset_filter = Q()

    children_qs = (
        RoadmapNode.objects.filter(
            roadmap=roadmap,
            parent=parent,
            status=Publication.PUBLISHED,
        )
        .filter(keyset_filter)
        .annotate(
            has_children=Exists(
                RoadmapNode.objects.filter(parent=OuterRef('pk'), status=Publication.PUBLISHED)
            )
        )
        .select_related('learning_topic')
        .order_by('position', 'pk')
    )

    fetch_limit = min(max(1, limit), 100)
    items = list(children_qs[:fetch_limit + 1])
    has_next = len(items) > fetch_limit
    if has_next:
        items = items[:fetch_limit]
        last_item = items[-1]
        next_cursor = make_cursor(
            roadmap.id, parent.id, roadmap.tree_revision, last_item.position, last_item.pk
        )
    else:
        next_cursor = None

    return serialize_node_list(roadmap, items, user), next_cursor


def get_node_learn_data(roadmap, node_id, user):
    """
    Fetch node learning data. Supports exercises-only fallback when a linked topic
    is draft, unauthorized, or absent.
    """
    node = get_effective_published_node(roadmap, node_id)
    if node is None:
        return None

    if user is None:
        user = AnonymousUser()

    topic = node.learning_topic
    topic_allowed = (
        topic is not None
        and topic.status == Publication.PUBLISHED
        and is_content_scoped_to_user(topic, user)
    )
    problem_links = list(
        node.problem_links.select_related('problem').order_by('position', 'pk')
    )
    candidate_pids = set(link.problem_id for link in problem_links)
    accessible_pids = get_accessible_problem_ids(user, candidate_pids)
    solved_pids = get_user_solved_problem_ids(user, accessible_pids)

    has_nonblank_intro = bool(topic_allowed and topic and topic.introduction and topic.introduction.strip())

    published_lessons = []
    if topic_allowed and topic:
        lessons_qs = topic.lessons.filter(status=Publication.PUBLISHED).order_by('position', 'pk')
        published_lessons = [l for l in lessons_qs if l.body and l.body.strip()]

    has_lessons = bool(published_lessons)
    has_exercises = bool(accessible_pids)

    content_state, _ = _evaluate_readiness_state(
        roadmap, node.id, has_nonblank_intro, has_lessons, has_exercises
    )
    if content_state != CONTENT_STATE_AVAILABLE:
        return None

    is_suppressed = False
    if user.is_authenticated:
        profile = getattr(user, 'profile', None)
        if profile is not None:
            c = getattr(profile, 'current_contest', None)
            if c is not None and not c.contest.can_join:
                is_suppressed = True

    if topic_allowed and topic:
        lessons_data = [
            {
                'id': lesson.id,
                'title': lesson.title,
                'slug': lesson.slug,
                'position': lesson.position,
                'summary': lesson.summary,
                'lesson_url': reverse('roadmap_node_lesson', args=[roadmap.slug, node.id, lesson.id]),
            }
            for lesson in published_lessons
        ]
        topic_data = {
            'id': topic.id,
            'name': topic.name,
            'slug': topic.slug,
            'introduction': topic.introduction,
            'content_revision': topic.content_revision,
        }
    else:
        lessons_data = []
        topic_data = None
    resume_lesson_url = None
    if published_lessons:
        if user.is_authenticated:
            last_state = (
                TopicLessonState.objects.filter(
                    user=user,
                    lesson_id__in=[l.id for l in published_lessons],
                )
                .order_by('-last_accessed_at')
                .first()
            )
            if last_state:
                resume_lesson_url = reverse('roadmap_node_lesson', args=[roadmap.slug, node.id, last_state.lesson_id])

    problems_data = []
    direct_pids = set()
    for link in problem_links:
        if link.problem_id in accessible_pids:
            prob = link.problem
            direct_pids.add(prob.id)
            problems_data.append({
                'id': prob.id,
                'code': prob.code,
                'name': prob.name,
                'position': link.position,
                'canonical_url': reverse('problem_detail', args=[prob.code]),
                'is_solved': (prob.id in solved_pids),
            })

    progress_data = _format_progress_dict(
        direct_pids, solved_pids, user, is_suppressed, scope='direct'
    )

    ancestors = list(node.get_ancestors(include_self=True))
    breadcrumb = [
        {
            'id': a.id,
            'title': a.title,
            'slug': a.slug,
            'focus_url': f"{reverse('roadmap_detail', args=[roadmap.slug])}?focus={a.id}",
        }
        for a in ancestors
    ]

    return {
        'node': {
            'id': node.id,
            'title': node.title,
            'slug': node.slug,
            'type': node.type,
            'difficulty': node.difficulty,
            'roadmap': {
                'id': roadmap.id,
                'slug': roadmap.slug,
                'title': roadmap.title,
            },
            'breadcrumb': breadcrumb,
        },
        'topic': topic_data,
        'lessons': lessons_data,
        'resume_lesson_url': resume_lesson_url,
        'problems': problems_data,
        'progress': progress_data,
    }


def get_node_lesson_data(roadmap, node_id, lesson_id, user):
    node = get_effective_published_node(roadmap, node_id)
    if node is None:
        return None

    if user is None:
        user = AnonymousUser()

    topic = node.learning_topic
    if topic is None or topic.status != Publication.PUBLISHED or not is_content_scoped_to_user(topic, user):
        return None

    lesson = TopicLesson.objects.filter(pk=lesson_id, topic=topic).first()
    if lesson is None or lesson.status != Publication.PUBLISHED or not (lesson.body and lesson.body.strip()):
        return None

    all_lessons = [
        l for l in topic.lessons.filter(status=Publication.PUBLISHED).order_by('position', 'pk')
        if l.body and l.body.strip()
    ]
    current_index = next((idx for idx, l in enumerate(all_lessons) if l.id == lesson.id), None)

    prev_url, next_url = None, None
    if current_index is not None:
        if current_index > 0:
            prev_l = all_lessons[current_index - 1]
            prev_url = reverse('roadmap_node_lesson', args=[roadmap.slug, node.id, prev_l.id])
        if current_index < len(all_lessons) - 1:
            next_l = all_lessons[current_index + 1]
            next_url = reverse('roadmap_node_lesson', args=[roadmap.slug, node.id, next_l.id])

    return {
        'node': {
            'id': node.id,
            'title': node.title,
            'slug': node.slug,
            'learn_url': reverse('roadmap_node_learn', args=[roadmap.slug, node.id]),
        },
        'topic': {'id': topic.id, 'name': topic.name, 'slug': topic.slug},
        'lesson': {
            'id': lesson.id,
            'title': lesson.title,
            'slug': lesson.slug,
            'position': lesson.position,
            'summary': lesson.summary,
            'body': lesson.body,
            'content_revision': lesson.content_revision,
        },
        'navigation': {'prev_lesson_url': prev_url, 'next_lesson_url': next_url},
        'lecture_state': (
            {
                'position_version': TopicLessonState.objects.filter(user=user, lesson=lesson).values_list('position_version', flat=True).first() or 0,
                'resume_offset': (
                    TopicLessonState.objects.filter(
                        user=user,
                        lesson=lesson,
                        content_revision=lesson.content_revision,
                    ).values_list('offset', flat=True).first()
                    or 0
                ),
                'messages': [
                    {
                        'role': m.role,
                        'content': m.content,
                        'created_at': m.created_at.isoformat(),
                    }
                    for m in reversed(
                        list(
                            TopicLessonQAMessage.objects.filter(
                                user=user,
                                lesson=lesson,
                                content_revision=lesson.content_revision,
                            ).order_by('-created_at', '-pk')[:40]
                        )
                    )
                ],
                'qa_url': reverse('roadmap_node_lesson_questions', args=[roadmap.slug, node.id, lesson.id]),
                'state_url': reverse('roadmap_node_lesson_state', args=[roadmap.slug, node.id, lesson.id]),
            }
            if user.is_authenticated
            else None
        ),
    }


def get_progress_data(roadmap, user, focus_node_id=None):
    snapshot = RoadmapSnapshot(user, roadmap)
    if not snapshot.accessible:
        return None

    now_iso = timezone.now().isoformat()
    if focus_node_id is not None:
        if focus_node_id not in snapshot.node_dict:
            return None

        return {
            'roadmap_id': snapshot.roadmap.id,
            'tree_revision': snapshot.roadmap.tree_revision,
            'node_id': focus_node_id,
            'timestamp': now_iso,
            'direct': snapshot.progress(focus_node_id, 'direct'),
            'subtree': snapshot.progress(focus_node_id, 'subtree'),
        }

    return {
        'roadmap_id': snapshot.roadmap.id,
        'tree_revision': snapshot.roadmap.tree_revision,
        'node_id': None,
        'timestamp': now_iso,
        'subtree': snapshot.overall_progress,
    }

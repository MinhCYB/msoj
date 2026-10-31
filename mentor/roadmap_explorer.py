"""Learner roadmap staged cross-topic path and contextual node selection explorer."""
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Exists, OuterRef
from django.http import Http404, HttpResponseBadRequest
from django.urls import reverse

from .roadmap_curriculum import ROADMAP_SLUG
from .roadmap_models import Publication, RoadmapNode, RoadmapPrerequisite, Visibility
from .roadmap_selectors import (
    TreeRevisionStale,
    get_effective_published_nodes_filter,
    parse_cursor,
    serialize_node_list,
)

def get_serialized_published_nodes(roadmap, user) -> List[Dict[str, Any]]:
    """Fetch and serialize all effective-published nodes for a roadmap."""
    effective_filter = get_effective_published_nodes_filter(roadmap)
    published_nodes = list(
        RoadmapNode.objects.filter(roadmap=roadmap)
        .filter(effective_filter)
        .annotate(has_children=Exists(
            RoadmapNode.objects.filter(parent=OuterRef('pk'), status=Publication.PUBLISHED)
        ))
        .select_related('learning_topic')
        .order_by('tree_id', 'lft')
    )
    return serialize_node_list(roadmap, published_nodes, user)


def build_prerequisite_graphs(roadmap, serialized_nodes: List[Dict[str, Any]]) -> Tuple[
    Dict[int, List[Tuple[int, str]]],
    Dict[int, List[Tuple[int, str]]],
    Dict[int, List[Dict[str, Any]]],
    bool,
]:
    """Build prerequisite and successor graphs from persisted roadmap edges."""
    id_map = {node['id']: node for node in serialized_nodes}
    published_ids = set(id_map)
    prereq_graph: Dict[int, List[Tuple[int, str]]] = {}
    successor_graph: Dict[int, List[Tuple[int, str]]] = {}
    missing_prereqs: Dict[int, List[Dict[str, Any]]] = {}
    is_canonical = (
        roadmap.slug == ROADMAP_SLUG
        and getattr(roadmap, 'visibility', None) == Visibility.PUBLIC
    )
    db_links = RoadmapPrerequisite.objects.filter(
        node__roadmap=roadmap,
        prerequisite__roadmap=roadmap,
    ).values_list('node_id', 'prerequisite_id', 'reason')
    for target_id, prerequisite_id, reason in db_links:
        if target_id not in published_ids:
            continue
        if prerequisite_id in published_ids:
            prereq_graph.setdefault(target_id, []).append((prerequisite_id, reason or ''))
            successor_graph.setdefault(prerequisite_id, []).append((target_id, reason or ''))
        else:
            missing_prereqs.setdefault(target_id, []).append({
                'id': prerequisite_id,
                'reason': reason or '',
            })
    return prereq_graph, successor_graph, missing_prereqs, is_canonical


def order_goals_topological(
    topic_nodes: List[Dict[str, Any]],
    prereq_graph: Dict[int, List[Tuple[int, str]]],
    successor_graph: Dict[int, List[Tuple[int, str]]],
) -> List[Dict[str, Any]]:
    """Order topic nodes so prerequisites appear before dependents where possible."""
    if not topic_nodes:
        return []

    topic_ids = {node['id'] for node in topic_nodes}
    topic_node_map = {node['id']: node for node in topic_nodes}
    original_index = {node['id']: i for i, node in enumerate(topic_nodes)}

    in_degree = {
        tid: sum(1 for pid, _ in prereq_graph.get(tid, []) if pid in topic_ids)
        for tid in topic_ids
    }

    ready = [node['id'] for node in topic_nodes if in_degree[node['id']] == 0]
    ordered_ids: List[int] = []
    visited: Set[int] = set()

    while ready:
        ready.sort(key=lambda nid: original_index[nid])
        curr_id = ready.pop(0)
        ordered_ids.append(curr_id)
        visited.add(curr_id)

        for sid, _ in successor_graph.get(curr_id, []):
            if sid in in_degree and sid not in visited:
                in_degree[sid] -= 1
                if in_degree[sid] == 0:
                    ready.append(sid)

    for node in topic_nodes:
        if node['id'] not in visited:
            ordered_ids.append(node['id'])

    return [topic_node_map[nid] for nid in ordered_ids]


def compute_goal_closure_and_stages(
    goal_id: int,
    id_map: Dict[int, Dict[str, Any]],
    prereq_graph: Dict[int, List[Tuple[int, str]]],
    missing_prereqs: Dict[int, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Computes prerequisite closure and topological layer stages for the given goal.
    Returns (stages, has_path).
    """
    closure: Set[int] = set()
    in_stack: Set[int] = set()
    has_cycle = False
    has_missing_in_closure = False

    def dfs(nid: int):
        nonlocal has_cycle, has_missing_in_closure
        closure.add(nid)
        in_stack.add(nid)
        if nid in missing_prereqs:
            has_missing_in_closure = True
        for pid, _ in prereq_graph.get(nid, []):
            if pid in in_stack:
                has_cycle = True
            elif pid not in closure:
                dfs(pid)
        in_stack.remove(nid)

    dfs(goal_id)

    has_path = not (has_cycle or has_missing_in_closure)

    if has_cycle or not closure:
        stages = [{
            'index': 0,
            'title': 'Mục tiêu',
            'nodes': [id_map[goal_id]] if goal_id in id_map else [],
        }]
        return stages, False

    memo_layer: Dict[int, int] = {}

    def get_layer(nid: int) -> int:
        if nid in memo_layer:
            return memo_layer[nid]
        prereqs = [pid for pid, _ in prereq_graph.get(nid, []) if pid in closure]
        if not prereqs:
            memo_layer[nid] = 0
            return 0
        layer_val = 1 + max(get_layer(p) for p in prereqs)
        memo_layer[nid] = layer_val
        return layer_val

    for nid in closure:
        get_layer(nid)

    max_layer = max(memo_layer.values()) if memo_layer else 0
    layers: List[List[int]] = [[] for _ in range(max_layer + 1)]
    for nid in closure:
        layers[memo_layer[nid]].append(nid)

    for layer in layers:
        layer.sort(key=lambda nid: (id_map[nid].get('position', 0), nid))

    num_stages = len(layers)
    if num_stages == 1:
        titles = ['Mục tiêu']
    elif num_stages == 2:
        titles = ['Chuẩn bị', 'Mục tiêu']
    elif num_stages == 3:
        titles = ['Chuẩn bị', 'Kết nối', 'Mục tiêu']
    else:
        titles = ['Chuẩn bị'] + [f'Chặng {i + 1}' for i in range(1, num_stages - 1)] + ['Mục tiêu']

    stages = [
        {
            'index': i,
            'title': titles[i],
            'nodes': [id_map[nid] for nid in layers[i]],
        }
        for i in range(num_stages)
    ]

    return stages, has_path


def find_default_goal(
    roadmap,
    topic_nodes: List[Dict[str, Any]],
    id_map: Dict[int, Dict[str, Any]],
    slug_map: Dict[str, Dict[str, Any]],
    prereq_graph: Dict[int, List[Tuple[int, str]]],
    missing_prereqs: Dict[int, List[Dict[str, Any]]],
    is_canonical: bool,
) -> Optional[Dict[str, Any]]:
    """
    Pick default goal topic: DFS when canonical and published+complete,
    otherwise earliest relational target, otherwise first topic.
    """
    if not topic_nodes:
        return None

    if is_canonical and 'dfs' in slug_map:
        dfs_node = slug_map['dfs']
        _, dfs_has_path = compute_goal_closure_and_stages(
            dfs_node['id'], id_map, prereq_graph, missing_prereqs
        )
        if dfs_has_path:
            return dfs_node

    for node in topic_nodes:
        if node['id'] in prereq_graph and prereq_graph[node['id']]:
            _, has_path = compute_goal_closure_and_stages(
                node['id'], id_map, prereq_graph, missing_prereqs
            )
            if has_path:
                return node

    for node in topic_nodes:
        if node['id'] in prereq_graph and prereq_graph[node['id']]:
            return node

    return topic_nodes[0]


def _build_group_journey(serialized_nodes, current_group, is_canonical):
    """Presentation guidance, not prerequisite edges or learner completion state."""
    if not is_canonical:
        return [], [], None
    definitions = (
        ('Xây nền tảng', ('foundations',)),
        ('Trang bị công cụ cốt lõi', ('basic-algorithms', 'data-structures', 'number-theory')),
        ('Mở rộng các hướng giải bài', ('dynamic-programming', 'graphs', 'trees', 'strings')),
        ('Đi sâu theo mục tiêu', ('geometry', 'flow-matching', 'games', 'advanced-search')),
    )
    root_groups = {node['slug']: node for node in serialized_nodes
                   if node['type'] == 'GROUP' and node.get('parent_id') is None}
    milestones = []
    assigned = set()
    for index, (title, slugs) in enumerate(definitions, start=1):
        nodes = [root_groups[slug] for slug in slugs if slug in root_groups]
        if not nodes:
            continue
        for node in nodes:
            assigned.add(node['id'])
        milestones.append({'number': index, 'title': title, 'nodes': nodes})
    parallel = [node for node in root_groups.values() if node['id'] not in assigned]

    id_map = {node['id']: node for node in serialized_nodes}
    root = current_group
    while root and root.get('parent_id'):
        root = id_map.get(root['parent_id'])
    current = next((milestone for milestone in milestones
                    if root and any(node['id'] == root['id'] for node in milestone['nodes'])), None)
    return milestones, parallel, current


def _prepare_topic_finder(nodes, is_canonical):
    aliases = {
        'dfs': ['depth first search'], 'bfs': ['breadth first search'],
        'dp-basics': ['dp', 'qhd', 'quy hoạch động', 'dynamic programming'],
        'segment-tree': ['cây đoạn', 'cay doan', 'segtree'],
        'fenwick-tree': ['bit', 'fenwick', 'binary indexed tree'],
        'binary-search': ['tknp'], 'lazy-propagation': ['lazy', 'đẩy lười'],
    }
    id_map = {node['id']: node for node in nodes}
    for node in nodes:
        if node['type'] != 'TOPIC':
            continue
        ancestors = []
        parent = id_map.get(node.get('parent_id'))
        while parent:
            ancestors.append(parent)
            parent = id_map.get(parent.get('parent_id'))
        ancestors.reverse()
        node['finder_path'] = ' → '.join(parent['title'] for parent in ancestors)
        node['finder_group'] = ancestors[0]['id'] if ancestors else ''
        node['finder_aliases'] = aliases.get(node['slug'], []) if is_canonical else []


def build_roadmap_explorer(request, roadmap) -> Dict[str, Any]:
    """
    Main entry point for explorer context resolution.
    Returns dictionary with 'explorer', 'focus', 'breadcrumb', 'map_url', etc.
    Raises Http404 for unknown/inaccessible IDs; returns HttpResponseBadRequest for bad params.
    """
    cursor = request.GET.get('cursor')
    limit_raw = request.GET.get('limit')
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
            if limit < 1:
                return HttpResponseBadRequest('Tham số limit không hợp lệ.')
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số limit không hợp lệ.')

    focus_raw = request.GET.get('focus')
    focus_id = None
    if focus_raw is not None:
        try:
            focus_id = int(focus_raw)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số focus không hợp lệ.')

    if cursor:
        try:
            parse_cursor(cursor, roadmap.id, focus_id, roadmap.tree_revision)
        except TreeRevisionStale:
            raise
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số con trỏ không hợp lệ.')

    serialized_nodes = get_serialized_published_nodes(roadmap, request.user)
    id_map = {node['id']: node for node in serialized_nodes}
    slug_map = {node['slug']: node for node in serialized_nodes}

    focus_node = None
    focus_model_obj = None
    if focus_id is not None:
        if focus_id not in id_map:
            raise Http404('Node không tồn tại hoặc chưa công khai.')
        focus_node = id_map[focus_id]
        focus_model_obj = RoadmapNode.objects.filter(pk=focus_id, roadmap=roadmap).first()

    prereq_graph, successor_graph, missing_prereqs, is_canonical = build_prerequisite_graphs(
        roadmap, serialized_nodes
    )

    raw_view = request.GET.get('view')
    if raw_view is not None:
        if raw_view not in ('path', 'catalog'):
            return HttpResponseBadRequest('Tham số view không hợp lệ.')
        mode = raw_view
    else:
        mode = 'catalog'

    groups = [node for node in serialized_nodes if node['type'] == 'GROUP']
    group_node = None
    raw_group = request.GET.get('group')
    if raw_group is not None:
        try:
            group_id = int(raw_group)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số group không hợp lệ.')
        if group_id not in id_map:
            raise Http404('Nhóm không tồn tại hoặc chưa công khai.')
        candidate = id_map[group_id]
        if candidate['type'] != 'GROUP' and not candidate.get('has_children'):
            return HttpResponseBadRequest('Node được chọn không có chuyên đề con.')
        group_node = candidate
    elif focus_node is not None:
        if focus_node['type'] == 'GROUP' or focus_node.get('has_children'):
            group_node = focus_node
        else:
            parent_id = focus_node.get('parent_id')
            if parent_id and parent_id in id_map:
                group_node = id_map[parent_id]

    selected_node = None
    raw_selected = request.GET.get('selected')
    if raw_selected is not None:
        try:
            selected_id = int(raw_selected)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số selected không hợp lệ.')
        if selected_id not in id_map:
            raise Http404('Node được chọn không tồn tại hoặc chưa công khai.')
        selected_node = id_map[selected_id]
    elif focus_node is not None:
        selected_node = focus_node

    topic_nodes = [node for node in serialized_nodes if node['type'] == 'TOPIC']
    ordered_goals = order_goals_topological(topic_nodes, prereq_graph, successor_graph)

    goal_node = None
    raw_goal = request.GET.get('goal')
    if raw_goal is not None:
        try:
            goal_id = int(raw_goal)
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số goal không hợp lệ.')
        if goal_id not in id_map:
            raise Http404('Mục tiêu không tồn tại hoặc chưa công khai.')
        cand_goal = id_map[goal_id]
        if cand_goal['type'] != 'TOPIC':
            return HttpResponseBadRequest('Mục tiêu phải là chuyên đề.')
        goal_node = cand_goal
    elif mode == 'path':
        goal_node = find_default_goal(
            roadmap, topic_nodes, id_map, slug_map, prereq_graph, missing_prereqs, is_canonical
        )

    stages: List[Dict[str, Any]] = []
    has_path = False
    if goal_node is not None:
        stages, has_path = compute_goal_closure_and_stages(
            goal_node['id'], id_map, prereq_graph, missing_prereqs
        )

    stage_index = 0
    raw_stage = request.GET.get('stage')
    if raw_stage is not None:
        try:
            stage_idx = int(raw_stage)
            if stage_idx < 0:
                return HttpResponseBadRequest('Tham số stage không hợp lệ.')
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Tham số stage không hợp lệ.')
        if stages:
            if stage_idx >= len(stages):
                return HttpResponseBadRequest('Chỉ số stage vượt quá số lượng giai đoạn.')
            stage_index = stage_idx
        else:
            if stage_idx > 0:
                return HttpResponseBadRequest('Chỉ số stage vượt quá số lượng giai đoạn.')
            stage_index = 0
    elif selected_node is not None and stages:
        for idx, stg in enumerate(stages):
            if any(n['id'] == selected_node['id'] for n in stg['nodes']):
                stage_index = idx
                break

    if mode == 'path':
        visible_nodes = stages[stage_index]['nodes'] if stages else []
    else:
        if group_node is not None:
            visible_nodes = [n for n in serialized_nodes if n.get('parent_id') == group_node['id']]
        else:
            visible_nodes = [n for n in serialized_nodes if n.get('parent_id') is None]

    prerequisites: List[Dict[str, Any]] = []
    successors: List[Dict[str, Any]] = []
    summary = ""

    if selected_node is not None:
        sel_id = selected_node['id']
        has_missing_for_selected = bool(missing_prereqs.get(sel_id))
        for pid, reason in prereq_graph.get(sel_id, []):
            safe_reason = "" if has_missing_for_selected else reason
            prerequisites.append({'node': id_map[pid], 'reason': safe_reason})
        for sid, reason in successor_graph.get(sel_id, []):
            has_missing_for_successor = bool(missing_prereqs.get(sid))
            successors.append({'node': id_map[sid], 'reason': '' if has_missing_for_successor else reason})
        summary = selected_node.get('summary', '') or ''

    map_url = reverse('roadmap_detail', args=[roadmap.slug])

    closure_node_stages: Dict[int, int] = {}
    for stg in stages:
        for stg_node in stg['nodes']:
            closure_node_stages[stg_node['id']] = stg['index']

    for node in serialized_nodes:
        nid = node['id']
        ntype = node['type']
        has_ch = node.get('has_children')

        if mode == 'path' and goal_node:
            if nid in closure_node_stages:
                target_stage = closure_node_stages[nid]
                node['selection_url'] = f"{map_url}?view=path&goal={goal_node['id']}&stage={target_stage}&selected={nid}"
            elif ntype == 'TOPIC':
                node['selection_url'] = f"{map_url}?view=path&goal={nid}&selected={nid}"
            elif ntype == 'GROUP' or has_ch:
                node['selection_url'] = f"{map_url}?view=catalog&group={nid}&selected={nid}"
            else:
                node['selection_url'] = f"{map_url}?selected={nid}"
        elif mode == 'catalog':
            if ntype == 'GROUP' or has_ch:
                node['selection_url'] = f"{map_url}?view=catalog&group={nid}&selected={nid}"
            else:
                g_param = f"&group={group_node['id']}" if group_node else ""
                node['selection_url'] = f"{map_url}?view=catalog{g_param}&selected={nid}"
        else:
            node['selection_url'] = f"{map_url}?selected={nid}"

        if ntype == 'TOPIC':
            node['path_url'] = f"{map_url}?view=path&goal={nid}"
        else:
            node['path_url'] = None

        if ntype == 'GROUP' or has_ch:
            node['catalog_url'] = f"{map_url}?view=catalog&group={nid}"
    catalog_sections = []
    if mode == 'catalog' and group_node:
        section_groups = {}
        unassigned = []
        for node in visible_nodes:
            section = (node.get('display_section') or '').strip()
            if section:
                section_groups.setdefault(section, []).append(node)
            else:
                unassigned.append(node)
        catalog_sections.extend(
            {'title': section, 'nodes': section_nodes}
            for section, section_nodes in section_groups.items()
        )
        if unassigned:
            catalog_sections.append({'title': 'Chuyên đề khác', 'nodes': unassigned})

    _prepare_topic_finder(serialized_nodes, is_canonical)
    journey, parallel_groups, current_milestone = _build_group_journey(
        serialized_nodes, group_node, is_canonical)

    explorer = {
        'mode': mode,
        'goal': goal_node,
        'goals': ordered_goals,
        'stages': stages,
        'stage_index': stage_index,
        'visible_nodes': visible_nodes,
        'catalog_sections': catalog_sections,
        'groups': groups,
        'group': group_node,
        'selected': selected_node,
        'prerequisites': prerequisites,
        'successors': successors,
        'has_path': has_path,
        'summary': summary,
        'journey': journey,
        'parallel_groups': parallel_groups,
        'current_milestone': current_milestone,
    }

    breadcrumb = []
    breadcrumb_node = selected_node or (goal_node if mode == 'path' else group_node)
    while breadcrumb_node is not None:
        breadcrumb.append(breadcrumb_node)
        breadcrumb_node = id_map.get(breadcrumb_node.get('parent_id'))
    breadcrumb.reverse()

    title = roadmap.title
    if focus_model_obj:
        title = focus_model_obj.title
    elif selected_node:
        title = selected_node['title']

    return {
        'explorer': explorer,
        'focus': focus_model_obj,
        'breadcrumb': breadcrumb,
        'map_url': map_url,
        'title': title,
    }

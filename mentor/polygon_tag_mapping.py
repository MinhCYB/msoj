"""Polygon tag -> MSOJ problem type/group mapping, named after the roadmap curriculum."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from judge.models import PolygonTagMapping, ProblemGroup, ProblemType
from mentor.roadmap_curriculum import load_curriculum_manifest

DEFAULT_MAP_PATH = Path(__file__).resolve().parent / 'polygon_tag_map.json'
NAME_MAX_LENGTH = 20  # ProblemType.name / ProblemGroup.name


class PolygonTagMapError(Exception):
    pass


def load_tag_map(path: Optional[Path] = None) -> Dict[str, Any]:
    with open(path or DEFAULT_MAP_PATH, encoding='utf-8') as f:
        return json.load(f)


def build_plan(tag_map: Optional[Dict[str, Any]] = None, manifest: Optional[Dict[str, Any]] = None) -> List[dict]:
    """
    Resolve every tag to concrete (type, group) names using the roadmap titles.
    Raises PolygonTagMapError when the map points at a missing node or a name does not fit the columns.
    """
    tag_map = tag_map or load_tag_map()
    manifest = manifest or load_curriculum_manifest()
    nodes = {n['slug']: n for n in manifest['nodes']}
    short_names = {k: v for k, v in tag_map.get('type_names', {}).items() if not k.startswith('_')}

    def root_of(slug):
        node = nodes[slug]
        while node['parent']:
            node = nodes[node['parent']]
        return node

    def type_name(slug):
        return short_names.get(slug, slug)

    errors = []
    plan = []
    for tag, slug in tag_map['tags'].items():
        if tag != tag.strip().lower():
            errors.append(f'tag {tag!r} must be lowercase and trimmed')
        if slug not in nodes:
            errors.append(f'tag {tag!r}: unknown roadmap node {slug!r}')
            continue
        too_long = [type_name(slug)] if len(type_name(slug)) > NAME_MAX_LENGTH else []
        group_root = root_of(slug)
        if len(group_root['slug']) > NAME_MAX_LENGTH:
            too_long.append(group_root['slug'])
        if too_long:
            errors.append(f'tag {tag!r}: name(s) over {NAME_MAX_LENGTH} chars: {", ".join(too_long)}')
            continue
        plan.append({
            'tag': tag,
            'type': (type_name(slug), nodes[slug]['title']),
            'group': (group_root['slug'], group_root['title']),
        })

    unmapped = {k for k in tag_map.get('unmapped', {}) if not k.startswith('_')}
    both = unmapped & set(tag_map['tags'])
    if both:
        errors.append('tags both mapped and unmapped: ' + ', '.join(sorted(both)))
    if errors:
        raise PolygonTagMapError('\n'.join(errors))
    return plan


def apply_plan(plan: List[dict]) -> Dict[str, List[str]]:
    """
    Create missing ProblemType / ProblemGroup / PolygonTagMapping rows. Existing rows are never
    modified, so names or mappings an admin has edited by hand survive a re-run.
    """
    created = {'types': [], 'groups': [], 'mappings': []}
    for entry in plan:
        name, full_name = entry['type']
        problem_type, was_created = ProblemType.objects.get_or_create(name=name, defaults={'full_name': full_name})
        if was_created:
            created['types'].append(name)
        group_name, group_full_name = entry['group']
        group, was_created = ProblemGroup.objects.get_or_create(name=group_name,
                                                                defaults={'full_name': group_full_name})
        if was_created:
            created['groups'].append(group_name)
        _, was_created = PolygonTagMapping.objects.get_or_create(
            tag=entry['tag'], defaults={'problem_type': problem_type, 'problem_group': group})
        if was_created:
            created['mappings'].append(entry['tag'])
    return created

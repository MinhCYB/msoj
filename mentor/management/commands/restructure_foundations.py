"""One-way, local-development cutover of the Foundations curriculum."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from judge.fixtures.beginner.catalog import REUSE, SECTION_NODES, load_problems
from judge.models import PolygonProblem, PolygonTagMapping, Problem, ProblemType
from judge.utils.polygon_sync import skip_tags_of
from mentor.polygon_tag_mapping import apply_plan, build_plan, load_tag_map
from mentor.roadmap_curriculum import load_curriculum_manifest
from mentor.roadmap_models import (
    LearningTopic, NodeProblem, Publication, Roadmap, RoadmapNode,
    RoadmapPrerequisite, TopicLesson, Visibility, lock_roadmap_forest,
)

RENAMES = {
    'programming-basics': 'loops', 'io-and-numeric-safety': 'io-basics',
    'arrays-and-strings': 'array-basics', 'casework': 'conditions',
}
MERGES = {'correctness': 'algorithmic-thinking', 'hardcode': 'brute-force'}
ADDITIONS = {'functions', 'string-basics', 'matrix-basics'}
# Content is unchanged when moving these lessons: preserve revision and learner state.
REFERENCES = {
    'programming-basics': ('implementation', 'programming-foundations-reference'),
    'io-and-numeric-safety': ('implementation', 'numeric-safety'),
    'arrays-and-strings': ('array-basics', 'arrays-strings-reference'),
    'casework': ('conditions', 'case-analysis'),
    'correctness': ('algorithmic-thinking', 'correctness'),
    'hardcode': ('brute-force', 'finite-domains'),
    'algorithmic-thinking': ('algorithmic-thinking', 'problem-solving-reference'),
    'implementation': ('implementation', 'implementation-reference'),
}


def _lesson_destination(old, slug):
    if slug.startswith('beginner-practice-'):
        section = slug.removeprefix('beginner-practice-')
        if section not in SECTION_NODES:
            raise CommandError(f'Unknown practice section {section}; no writes.')
        return SECTION_NODES[section], slug
    if old in REFERENCES and slug == 'overview':
        return REFERENCES[old]
    return MERGES.get(old, RENAMES.get(old, old)), slug


def _legacy_skill_nodes(problem, old, tag_map):
    fallback = 'implementation' if old == 'programming-basics' else 'array-basics'
    source = PolygonProblem.objects.filter(problem=problem).first()
    allowed = set(RENAMES.values()) | ADDITIONS | {'implementation'}
    skills = {tag_map.get(tag.lower()) for tag in source.tags} & allowed if source else set()
    if len(skills) > 1:
        skills.discard('implementation')
    return sorted(skills) or [fallback]


class Command(BaseCommand):
    help = 'Restructure Foundations on local DEBUG dev; dry-run by default, preserving lesson/submission IDs.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--development', action='store_true')
        parser.add_argument('--user')

    @transaction.atomic
    def handle(self, *args, **options):
        manifest = load_curriculum_manifest()
        expected = {n['slug']: n for n in manifest['nodes']}
        roadmap = Roadmap.objects.filter(slug=manifest['roadmap']['slug']).first()
        if roadmap is None or roadmap.status != Publication.PUBLISHED or roadmap.visibility != Visibility.PUBLIC:
            raise CommandError('The public, published CP roadmap must already exist.')
        lock_roadmap_forest()
        nodes = {n.slug: n for n in roadmap.nodes.select_related('learning_topic')}
        legacy_slugs = (set(expected) - set(RENAMES.values()) - ADDITIONS) | set(RENAMES) | set(MERGES)
        if set(nodes) == set(expected):
            for slug, node in nodes.items():
                spec = expected[slug]
                parent = nodes.get(spec['parent'])
                if (node.parent_id, node.title, node.position, node.type) != (
                        parent.pk if parent else None, spec['title'], spec['position'], spec['type']):
                    raise CommandError(f'Canonical tree differs at {slug}; refusing to overwrite edits.')
            self.stdout.write('Already converted; no writes.')
            return
        if set(nodes) != legacy_slugs:
            raise CommandError('Runtime tree is neither the original nor converted catalog; no writes.')
        topic_ids = [n.learning_topic_id for n in nodes.values() if n.learning_topic_id]
        if (len(topic_ids) != len(set(topic_ids)) or
                RoadmapNode.objects.filter(learning_topic_id__in=topic_ids).exclude(roadmap=roadmap).exists()):
            raise CommandError('A topic is shared; refusing to move its lessons.')
        for old in RENAMES:
            if LearningTopic.objects.filter(slug='cp-' + RENAMES[old]).exists():
                raise CommandError(f'Target topic slug already exists: {RENAMES[old]}')
        for slug in ADDITIONS:
            if LearningTopic.objects.filter(slug='cp-' + slug).exists():
                raise CommandError(f'Target topic slug already exists: {slug}')
        specs = load_problems() + REUSE
        for spec in specs:
            if any(slug not in expected for slug in spec['nodes']):
                raise CommandError(f'Invalid practice placement for {spec["code"]}; no writes.')
        for source in PolygonProblem.objects.filter(problem__code__in=[spec['code'] for spec in specs]):
            if (source.status == PolygonProblem.SKIPPED or skip_tags_of(source.tags) or
                    source.owner.lower() in {owner.lower() for owner in settings.POLYGON_SKIP_OWNERS}):
                raise CommandError(f'Refusing to place excluded problem {source.problem_id}; no writes.')
        lesson_targets = set()
        for old, source in nodes.items():
            if source.learning_topic_id:
                for lesson in source.learning_topic.lessons.all():
                    target = _lesson_destination(old, lesson.slug)
                    if target in lesson_targets:
                        raise CommandError(f'Lesson collision at {target[0]}/{target[1]}; no writes.')
                    lesson_targets.add(target)
        self.stdout.write('Plan: retain renamed node IDs; add 3 topics; merge correctness/hardcode; move queries; redistribute practice and taxonomy.')
        if not options['apply']:
            self.stdout.write('DRY-RUN: no writes. Use --apply --development --user <staff>.')
            return
        if not (options['development'] and settings.DEBUG and
                settings.DATABASES['default'].get('HOST', '') in ('', 'localhost', '127.0.0.1', '::1')):
            raise CommandError('Writes require --development, DEBUG=True and local database.')
        user = get_user_model().objects.filter(username=options['user'], is_active=True, is_staff=True).first()
        permissions = ('mentor.add_learningtopic', 'mentor.change_learningtopic', 'mentor.delete_learningtopic',
                       'mentor.add_topiclesson', 'mentor.change_topiclesson', 'mentor.add_roadmapnode',
                       'mentor.change_roadmapnode', 'mentor.delete_roadmapnode', 'mentor.change_roadmap',
                       'mentor.add_nodeproblem', 'mentor.delete_nodeproblem',
                       'mentor.add_roadmapprerequisite', 'mentor.delete_roadmapprerequisite',
                       'mentor.publish_roadmap', 'judge.change_problem', 'judge.add_problemtype',
                       'judge.change_problemtype', 'judge.delete_problemtype', 'judge.add_problemgroup',
                       'judge.add_polygontagmapping', 'judge.change_polygontagmapping')
        if user is None or not user.has_perms(permissions):
            raise CommandError('An existing active staff author with curriculum/taxonomy permissions is required.')
        notes = json.loads((Path(__file__).resolve().parents[2] / 'theory_notes.json').read_text())
        note_map = {n['node_slug']: n for n in notes}
        original = dict(nodes)
        for old, new in RENAMES.items():
            node = nodes.pop(old)
            node.slug = new
            topic = node.learning_topic
            if topic:
                topic.slug = 'cp-' + new
                topic.save()
            nodes[new] = node
        for slug in ADDITIONS:
            spec = expected[slug]
            nodes[slug] = RoadmapNode.objects.create(
                roadmap=roadmap, slug=slug, title=spec['title'], type='TOPIC',
                parent=nodes[spec['parent']], position=spec['position'], status=Publication.PUBLISHED)
        affected = (set(RENAMES.values()) | ADDITIONS | set(MERGES.values()) |
                    {'algorithmic-thinking', 'implementation', 'queries'})
        for slug, node in nodes.items():
            if slug in MERGES:
                continue
            spec = expected[slug]
            node.summary = spec.get('introduction', '') or ''
            node.display_section = {
                'foundations-7': 'Nhập môn lập trình',
                'foundations-3': 'Kỹ năng giải bài nền tảng',
            }.get(spec.get('display_section', ''), '')
            if slug not in affected:
                if node.parent_id == nodes['range-queries'].pk or slug == 'complexity':
                    node.position = expected[slug]['position']
                    node.title = expected[slug]['title']
                node.save()
                continue
            spec = expected[slug]
            node.title, node.position, node.type = spec['title'], spec['position'], spec['type']
            node.difficulty = spec.get('difficulty')
            node.parent_id = nodes[spec['parent']].pk if spec['parent'] else None
            if spec['type'] == 'TOPIC':
                note = note_map[slug]
                topic = node.learning_topic
                if topic is None:
                    topic = LearningTopic(slug='cp-' + slug, status=Publication.PUBLISHED, visibility=Visibility.PUBLIC)
                topic.name, topic.introduction = node.title.split(' (')[0], note['introduction']
                topic.save()
                node.learning_topic = topic
            node.save()
        # Move, do not copy/recreate: all reading state, Q&A and attempts retain their lesson FK.
        changed_topics = set()
        for old, source in original.items():
            if not source.learning_topic_id or source.type != 'TOPIC':
                continue
            for lesson in list(source.learning_topic.lessons.all()):
                target_slug, lesson_slug = _lesson_destination(old, lesson.slug)
                target = nodes[target_slug].learning_topic
                if lesson.topic_id == target.pk and lesson.slug == lesson_slug:
                    continue
                if TopicLesson.objects.filter(topic=target, slug=lesson_slug).exclude(pk=lesson.pk).exists():
                    raise CommandError(f'Lesson collision at {target_slug}/{lesson_slug}; transaction rolled back.')
                TopicLesson.objects.filter(pk=lesson.pk).update(topic=target, slug=lesson_slug)
                changed_topics.update((source.learning_topic_id, target.pk))
        for slug, node in nodes.items():
            if slug in MERGES or slug not in affected or node.type != 'TOPIC':
                continue
            note = note_map[slug]
            lessons = [dict(note, slug='overview')] + note.get('lessons', [])
            for position, payload in enumerate(lessons):
                if not node.learning_topic.lessons.filter(slug=payload['slug']).exists():
                    TopicLesson.objects.create(topic=node.learning_topic, slug=payload['slug'],
                        title=payload['title'], summary=payload['summary'], body=payload['body'],
                        position=position, status=Publication.PUBLISHED)
            for position, lesson in enumerate(node.learning_topic.lessons.exclude(slug='overview').order_by('position', 'pk'), 1):
                TopicLesson.objects.filter(pk=lesson.pk).update(position=position)
        LearningTopic.objects.filter(pk__in=changed_topics).update(content_revision=F('content_revision') + 1)
        curated_codes = {s['code'] for s in specs}
        touched_ids = [n.pk for slug, n in original.items() if n.parent_id == original['foundations'].pk]
        NodeProblem.objects.filter(node_id__in=touched_ids, problem__code__in=curated_codes).delete()
        for position, spec in enumerate(specs):
            problem = Problem.objects.filter(code=spec['code'], deleted_at__isnull=True).first()
            if problem:
                for slug in spec['nodes']:
                    NodeProblem.objects.get_or_create(node=nodes[slug], problem=problem, defaults={'position': position})
        tag_map = load_tag_map()['tags']
        for old, source in original.items():
            if old not in RENAMES and old not in MERGES:
                continue
            for link in list(source.problem_links.exclude(problem__code__in=curated_codes)):
                targets = (_legacy_skill_nodes(link.problem, old, tag_map)
                           if old in ('programming-basics', 'arrays-and-strings')
                           else [MERGES.get(old, RENAMES.get(old, old))])
                for target in targets:
                    NodeProblem.objects.get_or_create(node=nodes[target], problem=link.problem,
                                                      defaults={'position': link.position})
                if source.pk not in {nodes[target].pk for target in targets}:
                    link.delete()
        for old, target_slug in MERGES.items():
            source, target = nodes[old], nodes[target_slug]
            edges = list(RoadmapPrerequisite.objects.filter(node=source)) + list(RoadmapPrerequisite.objects.filter(prerequisite=source))
            for edge in edges:
                nid = target.pk if edge.node_id == source.pk else edge.node_id
                pid = target.pk if edge.prerequisite_id == source.pk else edge.prerequisite_id
                edge.delete()
                if nid != pid:
                    RoadmapPrerequisite.objects.get_or_create(node_id=nid, prerequisite_id=pid,
                        defaults={'reason': edge.reason})
            topic = source.learning_topic
            source.delete()
            if topic and not topic.roadmap_nodes.exists():
                topic.delete()
        # Generic Polygon `basic` belongs to implementation, never to every beginner skill.
        plan = build_plan()
        apply_plan(plan)
        for entry in plan:
            PolygonTagMapping.objects.filter(tag=entry['tag'],
                problem_type__name__in=('programming-basics', 'arrays-and-strings')).update(
                    problem_type=ProblemType.objects.get(name=entry['type'][0]))
        for old, new in {'programming-basics': 'implementation', 'arrays-and-strings': 'array-basics'}.items():
            old_type = ProblemType.objects.filter(name=old).first()
            if old_type:
                target_type = ProblemType.objects.get(name=new)
                for problem in Problem.objects.filter(types=old_type):
                    skills = _legacy_skill_nodes(problem, old, tag_map)
                    problem.types.add(*ProblemType.objects.filter(name__in=skills))
                PolygonTagMapping.objects.filter(problem_type=old_type).update(problem_type=target_type)
                old_type.delete()
        for spec in specs:
            problem = Problem.objects.filter(code=spec['code'], deleted_at__isnull=True).first()
            if problem:
                # Remove generic fallback classification only for the explicitly curated beginner pack.
                problem.types.remove(*ProblemType.objects.filter(name='implementation'))
                problem.types.add(*ProblemType.objects.filter(name__in=spec['tags']))
        Roadmap.objects.filter(pk=roadmap.pk).update(tree_revision=F('tree_revision') + 1)
        self.stdout.write(self.style.SUCCESS('Converted Foundations; lesson IDs/revisions, problems and submissions retained.'))

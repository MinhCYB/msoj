"""Populate the existing development curriculum with original introductory notes."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mentor.roadmap_curriculum import load_curriculum_manifest
from mentor.roadmap_models import (
    LearningTopic, Publication, Roadmap, TopicLesson, Visibility,
    lock_roadmap_forest,
)
from mentor.roadmap_services import save_content, save_node

NOTES_PATH = Path(__file__).resolve().parents[2] / 'theory_notes.json'


class Command(BaseCommand):
    help = ('Seed original introductory theory into existing CP TOPIC nodes. '
            'Dry-run by default; --apply --development --user requires local DEBUG runtime. '
            'Never overwrites existing authored content or changes the curriculum tree.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--development', action='store_true')
        parser.add_argument('--user')

    def handle(self, *args, **options):
        try:
            notes = json.loads(NOTES_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read theory notes: {exc}') from exc
        catalog = load_curriculum_manifest()
        topics = {n['slug']: n for n in catalog['nodes'] if n['type'] == 'TOPIC'}
        if not isinstance(notes, list) or any(not isinstance(n, dict) for n in notes):
            raise CommandError('Theory notes must be a list of records.')
        slugs = [n.get('node_slug') for n in notes]
        if any(not isinstance(slug, str) or not slug for slug in slugs):
            raise CommandError('Every theory record needs a non-empty node_slug.')
        if len(slugs) != len(set(slugs)) or set(slugs) != set(topics):
            raise CommandError('Theory notes must cover every curriculum TOPIC exactly once.')
        for note in notes:
            for key in ('title', 'summary', 'body', 'introduction'):
                if not isinstance(note.get(key), str) or not note[key].strip():
                    raise CommandError(f'Missing {key} for {note["node_slug"]}.')
            if len(note['title']) > 200 or len('cp-' + note['node_slug']) > 100:
                raise CommandError(f'Invalid title or slug length for {note["node_slug"]}.')
            extras = note.get('lessons', [])
            if not isinstance(extras, list):
                raise CommandError(f'Invalid supplementary lessons for {note["node_slug"]}.')
            extra_slugs = [lesson.get('slug') for lesson in extras if isinstance(lesson, dict)]
            if len(extra_slugs) != len(extras) or len(set(extra_slugs)) != len(extras) or 'overview' in extra_slugs:
                raise CommandError(f'Invalid supplementary lesson slugs for {note["node_slug"]}.')
            for lesson in extras:
                if any(not isinstance(lesson.get(key), str) or not lesson[key].strip()
                       for key in ('slug', 'title', 'summary', 'body')):
                    raise CommandError(f'Incomplete supplementary lesson for {note["node_slug"]}.')

        user = None
        if options['apply']:
            database = settings.DATABASES['default']
            if not (options['development'] and settings.DEBUG and
                    database.get('HOST', '') in ('', 'localhost', '127.0.0.1', '::1')):
                raise CommandError('Writes require --development, DEBUG=True and a local database.')
            if not options['user']:
                raise CommandError('--apply requires --user with existing active staff permissions.')
            user = get_user_model().objects.filter(username=options['user'], is_active=True, is_staff=True).first()
            permissions = ('mentor.add_learningtopic', 'mentor.add_topiclesson',
                           'mentor.change_roadmapnode', 'mentor.publish_roadmap')
            if user is None or not user.has_perms(permissions):
                raise CommandError('User lacks active staff authoring/publication permissions.')

        with transaction.atomic():
            if options['apply']:
                lock_roadmap_forest()
            roadmap = Roadmap.objects.filter(slug=catalog['roadmap']['slug']).first()
            if roadmap is None or roadmap.status != Publication.PUBLISHED or roadmap.visibility != Visibility.PUBLIC:
                raise CommandError('The published public CP roadmap must already exist.')
            nodes = {n.slug: n for n in roadmap.nodes.select_related('learning_topic')}
            parent_slugs = {node.pk: node.slug for node in nodes.values()}
            expected = {n['slug']: n for n in catalog['nodes']}
            if set(nodes) != set(expected):
                raise CommandError('Runtime tree differs from approved curriculum inventory.')
            for slug, node in nodes.items():
                entry = expected[slug]
                parent_slug = parent_slugs.get(node.parent_id)
                if (node.title, node.type, node.difficulty, parent_slug, node.position, node.status) != (
                        entry['title'], entry['type'], entry['difficulty'], entry['parent'],
                        entry['position'], Publication.PUBLISHED):
                    raise CommandError(f'Runtime tree/publication differs at {slug}; no writes performed.')
            creations = []
            matched = 0
            for note in notes:
                node = nodes[note['node_slug']]
                topic_slug = 'cp-' + node.slug
                topic = LearningTopic.objects.filter(slug=topic_slug).first()
                if node.learning_topic_id is not None:
                    if topic is None or node.learning_topic_id != topic.pk:
                        raise CommandError(f'{node.slug} already has other authored content; refusing overwrite.')
                    expected_lessons = [dict(note, slug='overview')] + note.get('lessons', [])
                    if (topic.name, topic.introduction, topic.status, topic.visibility,
                        topic.organization_id, topic.roadmap_nodes.count()) != (
                            node.title.split(' (')[0], note['introduction'], Publication.PUBLISHED,
                            Visibility.PUBLIC, None, 1):
                        raise CommandError(f'{node.slug} contains edits or shared content; keep them, no writes performed.')
                    for position, payload in enumerate(expected_lessons):
                        lesson = topic.lessons.filter(slug=payload['slug']).first()
                        if lesson is None or (lesson.title, lesson.summary, lesson.body, lesson.status) != (
                                payload['title'], payload['summary'], payload['body'], Publication.PUBLISHED):
                            raise CommandError(f'{node.slug} contains edits or shared content; keep them, no writes performed.')
                    matched += 1
                elif topic is not None:
                    raise CommandError(f'Topic slug {topic_slug} exists without expected placement; refusing reuse.')
                else:
                    creations.append((node, note, topic_slug))
            self.stdout.write(f'TOPIC coverage: {len(notes)}; create: {len(creations)}; unchanged: {matched}; GROUPs untouched: {len(nodes) - len(notes)}')
            if not options['apply']:
                self.stdout.write('DRY-RUN: no writes. Use --apply --development --user <staff> on local development only.')
                return
            for node, note, topic_slug in creations:
                topic = save_content(user, LearningTopic(
                    name=node.title.split(' (')[0], slug=topic_slug, introduction=note['introduction'],
                    status=Publication.PUBLISHED, visibility=Visibility.PUBLIC,
                ))
                for position, payload in enumerate([dict(note, slug='overview')] + note.get('lessons', [])):
                    save_content(user, TopicLesson(
                        topic=topic, title=payload['title'], slug=payload['slug'], summary=payload['summary'],
                        body=payload['body'], position=position, status=Publication.PUBLISHED,
                    ))
                node.learning_topic = topic
                save_node(user, node)
            self.stdout.write(self.style.SUCCESS(f'Applied {len(creations)} topic/lesson placements. No problems or prerequisite edges added.'))

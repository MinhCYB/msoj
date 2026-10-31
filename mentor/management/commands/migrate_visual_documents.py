"""Audit and explicitly migrate legacy visual fences in selected lessons."""
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from mentor.lesson_visuals import visual_blocks, validate_visual_blocks
from mentor.roadmap_models import TopicLesson, lock_roadmap_forest
from mentor.roadmap_services import save_content
from mentor.visual_documents import convert_legacy, validate_document


def convert_body(body):
    replacements = []
    for start, end, raw in visual_blocks(body):
        if raw is None:
            raise ValueError('Unclosed msoj-visual fence.')
        config = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Invalid JSON constant {value}.')))
        if isinstance(config, dict) and config.get('version') == 2:
            validate_document(config)
            continue
        document = convert_legacy(config)
        rendered = '```msoj-visual\n' + json.dumps(document, ensure_ascii=False, indent=2) + '\n```'
        replacements.append((start, end, rendered))
    for start, end, replacement in reversed(replacements):
        body = body[:start] + replacement + body[end:]
    validate_visual_blocks(body)
    return body, len(replacements)


def _record(lesson):
    return {
        'id': lesson.pk,
        'revision': lesson.content_revision,
        'status': lesson.status,
        'body': lesson.body,
        'summary': lesson.summary,
        'body_sha256': hashlib.sha256(lesson.body.encode('utf-8')).hexdigest(),
        'summary_sha256': hashlib.sha256(lesson.summary.encode('utf-8')).hexdigest(),
    }


class Command(BaseCommand):
    help = 'Audit legacy visual fences; apply only with local DB, exact backup snapshot and staff author.'

    def add_arguments(self, parser):
        parser.add_argument('--lesson', action='append', type=int, dest='lessons')
        parser.add_argument('--backup', help='Private JSON backup/audit snapshot path.')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--development', action='store_true')
        parser.add_argument('--user')

    def handle(self, *args, **options):
        ids = tuple(sorted(set(options['lessons'] or ())))
        if not ids:
            raise CommandError('Specify one or more --lesson IDs; the command never scans all lessons.')
        if options['apply']:
            database = settings.DATABASES['default']
            if not (options['development'] and settings.DEBUG and
                    connection.vendor in ('sqlite', 'mysql') and
                    database.get('HOST', '') in ('', 'localhost', '127.0.0.1', '::1')):
                raise CommandError('Writes require --development, DEBUG=True and local SQLite/MySQL.')
            if not options['backup']:
                raise CommandError('--apply requires --backup pointing to the unchanged audit snapshot.')
            user = get_user_model().objects.filter(username=options['user'], is_active=True, is_staff=True).first()
            if user is None or not user.has_perms(('mentor.change_topiclesson', 'mentor.publish_roadmap')):
                raise CommandError('--apply requires active staff lesson-edit and publication permissions.')
        else:
            user = None

        with transaction.atomic():
            if options['apply']:
                lock_roadmap_forest()
            query = TopicLesson.objects.filter(pk__in=ids).select_related('topic').order_by('pk')
            if options['apply']:
                query = query.select_for_update()
            lessons = list(query)
            if {lesson.pk for lesson in lessons} != set(ids):
                raise CommandError('One or more lesson IDs do not exist; no changes made.')

            records, plans = [], []
            for lesson in lessons:
                converted_body, body_count = convert_body(lesson.body)
                converted_summary, summary_count = convert_body(lesson.summary)
                records.append(_record(lesson))
                plans.append((lesson, converted_body, body_count, converted_summary, summary_count))
                self.stdout.write(
                    f'Lesson {lesson.pk} ({lesson.slug}): {body_count} body and {summary_count} summary fences; '
                    f'{lesson.status}, revision {lesson.content_revision}.'
                )

            if not options['apply']:
                if options['backup']:
                    path = Path(options['backup'])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                        json.dump({'version': 1, 'lesson_ids': list(ids), 'records': records}, stream, ensure_ascii=False, indent=2)
                        stream.write('\n')
                    self.stdout.write(f'Private audit snapshot created: {path}')
                self.stdout.write('DRY-RUN only. No database writes performed.')
                return

            try:
                snapshot = json.loads(Path(options['backup']).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise CommandError(f'Cannot read backup snapshot: {exc}') from exc
            if snapshot.get('version') != 1 or snapshot.get('lesson_ids') != list(ids) or snapshot.get('records') != records:
                raise CommandError('Lesson body/summary/status/revision differs from audit snapshot; no writes performed.')

            for lesson, body, body_count, summary, summary_count in plans:
                if not body_count and not summary_count:
                    continue
                old_status = lesson.status
                lesson.body = body
                lesson.summary = summary
                save_content(user, lesson)
                if lesson.status != old_status:
                    raise CommandError(f'Publication state changed unexpectedly for lesson {lesson.pk}.')
            self.stdout.write(self.style.SUCCESS('Legacy visual conversion applied; publication states preserved.'))

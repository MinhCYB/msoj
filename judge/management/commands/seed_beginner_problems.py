"""Author, upload and curate the original MSOJ beginner problem pack."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from judge.fixtures.beginner.catalog import (
    REUSE, ROADMAP, SECTIONS, SOURCE, TAG_NAMES, export_problems, load_problems, statement, tutorial,
)
from judge.fixtures.beginner.validators import validator_source
from judge.models import PolygonProblem, PolygonTagMapping, Problem, ProblemGroup, ProblemType, Profile, Solution
from judge.utils.polygon_api import PolygonClient
from judge.utils.polygon_sync import PolygonSync, skip_tags_of
from mentor.roadmap_models import NodeProblem, Publication, Roadmap, TopicLesson
from mentor.roadmap_services import save_content, save_problem_link


class Command(BaseCommand):
    help = ('Prepare the original beginner pack. Default is read-only inventory. '
            '--export writes a private authoring directory, --upload writes Polygon, '
            '--apply imports the selected READY packages and curates private MSOJ problems.')

    def add_arguments(self, parser):
        parser.add_argument('codes', nargs='*')
        parser.add_argument('--export', dest='export_directory')
        parser.add_argument('--upload', action='store_true')
        parser.add_argument('--refresh-authored', action='store_true', help='Refresh marked Polygon statements/tutorials and append reviewed cases.')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user')
        parser.add_argument('--report', help='Private JSON file for resumable Polygon identifiers; required with --upload.')

    def handle(self, *args, **options):
        try:
            specs = load_problems()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        by_code = {p['code']: p for p in specs}
        unknown = set(options['codes']) - set(by_code)
        if unknown:
            raise CommandError('Unknown pack codes: ' + ', '.join(sorted(unknown)))
        selected = [p for p in specs if not options['codes'] or p['code'] in options['codes']]
        for spec in selected:
            self.stdout.write(f'{spec["code"]}: {spec["title"]} [{", ".join(spec["tags"])}] — {len(spec["cases"])} tests')
        self.stdout.write(f'{len(selected)} new exercises; {len(REUSE)} existing exercises; 10 practice sections (functions reuse four exercises).')
        if options['export_directory']:
            export_problems(options['export_directory'], selected)
            self.stdout.write('Exported authoring sources and deterministic test archives.')
        if not options['upload'] and not options['refresh_authored'] and not options['apply']:
            return
        user = get_user_model().objects.filter(username=options['user'], is_active=True, is_staff=True).first()
        permissions = ('judge.add_problem', 'judge.change_problem', 'mentor.add_nodeproblem',
                       'mentor.change_roadmapnode', 'mentor.add_topiclesson', 'mentor.change_topiclesson')
        if user is None or not user.has_perms(permissions):
            raise CommandError('An active staff --user with problem and roadmap authoring permissions is required.')
        client = PolygonClient()
        if options['upload'] or options['refresh_authored']:
            if not options['report']:
                raise CommandError('--upload requires a private --report path.')
            from judge.utils.beginner_polygon import refresh_authored_content, upload_problem
            report_path = Path(options['report'])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            rows = json.loads(report_path.read_text()) if report_path.exists() else {}
            for spec in selected:
                self.stdout.write(f'Uploading {spec["code"]}...', ending='\n')
                self.stdout.flush()
                if options['refresh_authored']:
                    result = refresh_authored_content(client, spec)
                else:
                    result = upload_problem(client, spec, validator_source(spec), wait_for_package=False)
                rows[spec['code']] = result
                report_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                report_path.chmod(0o600)
                self.stdout.write(f'{spec["code"]}: Polygon {result["id"]}; verified full package requested.')
                self.stdout.flush()
        if options['apply']:
            self._apply(user, client, selected, specs)

    def _apply(self, user, client, selected, all_specs):
        # Mapping only for this authored pack; do not change mappings for old Polygon aliases.
        with transaction.atomic():
            for spec in selected:
                group = ProblemGroup.objects.get(name=spec['group'])
                for tag in spec['tags']:
                    category, _ = ProblemType.objects.get_or_create(name=tag, defaults={'full_name': TAG_NAMES.get(tag, tag)})
                    mapping = PolygonTagMapping.objects.filter(tag=tag).first()
                    if mapping is None:
                        mapped_group = None if tag in TAG_NAMES and tag != 'modulo' else group
                        PolygonTagMapping.objects.create(tag=tag, problem_type=category, problem_group=mapped_group)
                    elif mapping.problem_type_id != category.pk:
                        raise CommandError(f'Existing Polygon tag mapping conflicts for {tag}; no override performed.')
        sync = PolygonSync(client=client, log=self.stdout.write)
        author = Profile.objects.get(user=user)
        remote = client.list_problems()
        selected_names = {p['code'].replace('_', '-'): p for p in selected}
        for name, spec in selected_names.items():
            candidates = [p for p in remote if p['name'] == name and p['owner'].lower() == settings.POLYGON_PREFERRED_OWNER.lower()]
            if len(candidates) != 1:
                raise CommandError(f'Expected one authored Polygon source for {name}.')
            item = candidates[0]
            if item.get('modified'):
                raise CommandError(f'{name}: uncommitted Polygon changes; finish upload before importing.')
            pp = sync._apply_remote(item, refresh_tags=True)
            if pp.owner.lower() in {o.lower() for o in settings.POLYGON_SKIP_OWNERS} or skip_tags_of(pp.tags):
                raise CommandError(f'{name} matches the skip policy.')
            current_revision = item.get('revision')
            ready = [p for p in client.packages(item['id']) if p.get('type') == 'linux'
                     and p.get('state') == 'READY' and p.get('revision') == current_revision]
            if not ready:
                raise CommandError(f'{name}: no linux/READY package for current revision {current_revision}.')
            existing = Problem.objects.filter(code=spec['code']).first()
            if existing is not None and existing.source != SOURCE:
                owned_import = PolygonProblem.objects.filter(problem=existing, polygon_id=item['id']).exists()
                if existing.source or not owned_import:
                    raise CommandError(f'Refusing to replace a pre-existing problem: {spec["code"]}')
            authored_update = False
            if existing is not None and existing.source == SOURCE:
                linked = PolygonProblem.objects.filter(problem=existing, polygon_id=item['id']).first()
                authored_update = linked is not None and linked.synced_revision != current_revision
                if authored_update and (existing.description != statement(spec) or existing.solution.content != tutorial(spec)):
                    raise CommandError(f'{name}: local authored edits differ; review before importing newer Polygon revision.')
            result = sync.sync_problem(pp, author=author)
            if result.status != PolygonProblem.SYNCED:
                raise CommandError(f'{name}: {result.status}: {result.message}')
            with transaction.atomic():
                problem = Problem.objects.get(pk=result.problem_id)
                # Preserve hand edits after the initial authored import.
                if not problem.source or authored_update:
                    problem.description = statement(spec)
                    problem.source = SOURCE
                    problem.points = 100
                    problem.is_public = False
                    problem.group = ProblemGroup.objects.get(name=spec['group'])
                    problem.full_clean(exclude=('allowed_languages', 'types', 'authors', 'curators', 'testers', 'tags', 'banned_users', 'deleted_at'))
                    problem.save()
                    solution, _ = Solution.objects.get_or_create(problem=problem)
                    solution.content = tutorial(spec)
                    solution.is_public = False
                    solution.publish_on = timezone.now()
                    solution.save()
                    solution.authors.add(author)
                problem.types.add(*ProblemType.objects.filter(name__in=spec['tags']))
        if Problem.objects.filter(code__in=[p['code'] for p in all_specs], source=SOURCE).count() == len(all_specs):
            self._curate(user, all_specs)
        self.stdout.write(self.style.SUCCESS('Imported private exercises, retained skill tags, and attached roadmap practice. No problems published.'))

    def _curate(self, user, specs):
        roadmap = Roadmap.objects.get(slug=ROADMAP)
        nodes = {node.slug: node for node in roadmap.nodes.select_related('learning_topic')}
        placements = {}
        with transaction.atomic():
            for entry in specs + REUSE:
                problem = Problem.objects.filter(code=entry['code'], deleted_at__isnull=True).first()
                if problem is None:
                    continue
                source = PolygonProblem.objects.filter(problem=problem).first()
                if source and (source.status == PolygonProblem.SKIPPED or
                               source.owner.lower() in {o.lower() for o in settings.POLYGON_SKIP_OWNERS} or skip_tags_of(source.tags)):
                    raise CommandError(f'Refusing to include skipped problem {problem.code}.')
                for tag in entry['tags']:
                    category, _ = ProblemType.objects.get_or_create(name=tag, defaults={'full_name': TAG_NAMES.get(tag, tag)})
                    problem.types.add(category)
                for slug in entry['nodes']:
                    placements.setdefault(slug, []).append(problem)
            for slug, problems in placements.items():
                node = nodes[slug]
                start = max(node.problem_links.values_list('position', flat=True), default=-1) + 1
                for offset, problem in enumerate(problems):
                    if not NodeProblem.objects.filter(node=node, problem=problem).exists():
                        save_problem_link(user, NodeProblem(node=node, problem=problem, position=start + offset))
            # Draft practice guides preserve the existing published theory and curriculum structure.
            section_entries = [(section, title, [p for p in specs if p['section'] == section] +
                                [p for p in REUSE if p['section'] == section]) for section, title in SECTIONS.items() if section != 'functions']
            section_entries.insert(4, ('functions', SECTIONS['functions'], [p for p in specs if p['function_practice']]))
            for position, (section, title, entries) in enumerate(section_entries, 1):
                node_slug = 'gcd-euclid' if section == 'numbers' else 'arrays-and-strings' if section in ('arrays', 'frequency', 'strings', 'matrices') else 'programming-basics'
                topic = nodes[node_slug].learning_topic
                if topic is None:
                    raise CommandError(f'Missing existing learning topic: {node_slug}')
                slug = 'beginner-practice-' + section
                lesson = TopicLesson.objects.filter(topic=topic, slug=slug).first()
                if lesson is not None:
                    missing = [entry for entry in entries if f'](/problem/{entry["code"]})' not in lesson.body]
                    if missing:
                        if lesson.status != Publication.DRAFT:
                            raise CommandError(f'{slug}: published practice guide needs editorial review before adding exercises.')
                        addition = '\n\n## Bài luyện bổ sung\n\n'
                        for entry in missing:
                            problem = Problem.objects.get(code=entry['code'])
                            addition += f'- [{problem.name}](/problem/{problem.code}) — `{problem.code}`\n'
                        lesson.body = lesson.body.rstrip() + addition
                        save_content(user, lesson)
                    continue
                body = 'Bộ bài luyện MSOJ dành cho người mới. Các bài mới đang ở trạng thái riêng tư để biên tập viên duyệt.\n\n'
                if section == 'functions':
                    body += ('Dùng lại bài đã học để tách phần xử lý thành hàm. Với mỗi hàm, nêu tham số, '
                             'giá trị trả về và phạm vi biến. Xem lời giải mẫu có hàm sau khi tự làm. '
                             'Bộ chấm chỉ đánh giá đầu ra, không bắt buộc cách tổ chức mã.\n\n')
                for entry in entries:
                    problem = Problem.objects.filter(code=entry['code']).first()
                    if problem:
                        body += f'- [{problem.name}](/problem/{problem.code}) — `{problem.code}`\n'
                save_content(user, TopicLesson(topic=topic, slug=slug, title=f'Luyện tập: {title}',
                                               summary=title, body=body, position=position, status=Publication.DRAFT))

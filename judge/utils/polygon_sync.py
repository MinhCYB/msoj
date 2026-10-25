import logging
import re
import zipfile
from collections import defaultdict
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone
from lxml import etree as ET

from judge.models import PolygonProblem, PolygonTagMapping, Problem, ProblemGroup, Profile
from judge.utils.codeforces_polygon import ImportPolygonError, PolygonImporter
from judge.utils.polygon_api import PolygonAPIError, PolygonClient

__all__ = ['PolygonSync', 'PolygonSyncError', 'normalize_code', 'map_tags']

logger = logging.getLogger('judge.polygon')

CODE_MAX_LENGTH = 32
# Polygon language name -> MSOJ site language. Anything else makes the importer fail for that problem.
POLYGON_TO_SITE_LANGUAGE = {'english': 'en', 'vietnamese': 'vi'}
# Order in which a statement language is preferred as the main one.
MAIN_LANGUAGE_PREFERENCE = ('english', 'vietnamese')
# A "full" package is one with generated tests; Polygon calls it "linux".
FULL_PACKAGE_TYPE = 'linux'


class PolygonSyncError(Exception):
    pass


def normalize_code(name: str) -> str:
    """Polygon names allow `-` and `.`; MSOJ codes are ^[a-z0-9_]+$ and at most 32 characters."""
    return re.sub(r'[^a-z0-9_]', '_', name.lower())[:CODE_MAX_LENGTH]


def _lower_set(values: Iterable[str]) -> set:
    return {v.lower() for v in values}


def skip_tags_of(tags: Iterable[str]) -> set:
    return _lower_set(tags) & _lower_set(settings.POLYGON_SKIP_TAGS)


def map_tags(tags: Iterable[str]) -> Tuple[Optional[ProblemGroup], list]:
    """Return (group, types) for Polygon tags. Group is taken from the first tag that maps to one."""
    ignored = _lower_set(settings.POLYGON_IGNORED_TAGS)
    keys = [t.lower() for t in tags if t.lower() not in ignored]
    mappings = {
        m.tag: m for m in PolygonTagMapping.objects.filter(tag__in=keys).select_related('problem_type', 'problem_group')
    }
    group, types = None, []
    for key in keys:
        mapping = mappings.get(key)
        if mapping is None:
            continue
        if group is None and mapping.problem_group is not None:
            group = mapping.problem_group
        if mapping.problem_type is not None and mapping.problem_type not in types:
            types.append(mapping.problem_type)
    return group, types


def pick_full_package(packages: List[dict]) -> Optional[dict]:
    ready = [p for p in packages if p.get('state') == 'READY' and p.get('type') == FULL_PACKAGE_TYPE]
    return max(ready, key=lambda p: (p['revision'], p['id']), default=None)


def statement_config(package: zipfile.ZipFile) -> dict:
    """Build the importer's non-interactive language config from the statements inside a package."""
    root = ET.fromstring(package.read('problem.xml'))
    languages = [s.get('language', 'unknown') for s in root.findall('.//statement[@type="application/x-tex"]')]
    main = next((lang for lang in MAIN_LANGUAGE_PREFERENCE if lang in languages), languages[0] if languages else None)
    site_map = {
        lang: POLYGON_TO_SITE_LANGUAGE[lang]
        for lang in languages if lang != main and lang in POLYGON_TO_SITE_LANGUAGE
    }
    return {
        'ignore_zero_point_batches': False,
        'ignore_zero_point_cases': False,
        'append_main_solution_to_tutorial': False,
        'main_tutorial_language': main,
        'main_statement_language': main,
        'polygon_to_site_language_map': site_map,
    }


class PolygonSync:
    def __init__(self, client: Optional[PolygonClient] = None, log: Optional[Callable[[str], None]] = None):
        self._client = client
        self.log = log or (lambda message: None)

    @property
    def client(self) -> PolygonClient:
        if self._client is None:
            self._client = PolygonClient()
        return self._client

    # ---- index -------------------------------------------------------------------------------------------

    def _apply_remote(self, item: dict, refresh_tags: bool) -> PolygonProblem:
        pp, _ = PolygonProblem.objects.get_or_create(polygon_id=item['id'], defaults={
            'owner': item['owner'], 'name': item['name'],
        })
        pp.owner = item['owner']
        pp.name = item['name']
        pp.code = normalize_code(item['name'])
        pp.latest_revision = item.get('latestPackage')
        revision = item.get('revision')
        pp.tags_error = ''
        pp.last_checked = timezone.now()
        if pp.owner.lower() in _lower_set(settings.POLYGON_SKIP_OWNERS):
            pp.tags_revision = None
            pp.save()
            return pp
        if refresh_tags or pp.tags_revision != revision:
            try:
                pp.tags = self.client.view_tags(item['id'])
                pp.tags_revision = revision
            except PolygonAPIError as e:
                # Without tags we cannot know whether the problem carries a skip tag, so it stays unsynced.
                pp.tags_revision = None
                pp.tags_error = str(e)
                logger.warning('Could not read tags of Polygon problem %s: %s', item['id'], e)
        pp.save()
        return pp

    def refresh_index(self, refresh_tags: bool = False) -> List[PolygonProblem]:
        """Pull the problem list and (for new/changed revisions) tags from Polygon, then classify."""
        remote = [item for item in self.client.list_problems() if not item.get('deleted')]
        self.log(f'Polygon lists {len(remote)} problems')
        rows = []
        for i, item in enumerate(remote, start=1):
            rows.append(self._apply_remote(item, refresh_tags))
            if i % 25 == 0:
                self.log(f'  indexed {i}/{len(remote)}')
        self.classify(rows)
        return rows

    def refresh_one(self, pp: PolygonProblem) -> PolygonProblem:
        items = self.client.call('problems.list', id=pp.polygon_id)
        if not items:
            raise PolygonSyncError(f'Polygon problem {pp.polygon_id} is no longer visible to this API key')
        pp = self._apply_remote(items[0], refresh_tags=False)
        self.classify([pp])
        pp.refresh_from_db()
        return pp

    # ---- classification ----------------------------------------------------------------------------------

    def classify(self, rows: Iterable[PolygonProblem]):
        """
        Assign a status to every row. Duplicates are resolved against all known non-skipped rows, not only
        `rows`, so classifying a single problem cannot make two problems claim the same code.
        """
        rows = list(rows)
        winners = self._winners({pp.code for pp in rows})
        for pp in rows:
            status, message = self._status_of(pp, winners)
            pp.status, pp.message = status, message
            if pp.problem_id is None and status in (PolygonProblem.NEW, PolygonProblem.CONFLICT):
                pp.synced_revision = None
            pp.save(update_fields=['status', 'message', 'synced_revision'])

    @staticmethod
    def _winners(codes: Iterable[str]) -> Dict[str, int]:
        by_code = defaultdict(list)
        skipped_owners = _lower_set(settings.POLYGON_SKIP_OWNERS)
        for pp in PolygonProblem.objects.filter(code__in=list(codes)):
            if pp.owner.lower() not in skipped_owners and not skip_tags_of(pp.tags):
                by_code[pp.code].append(pp)
        winners = {}
        for code, group in by_code.items():
            preferred = [pp for pp in group if pp.owner == settings.POLYGON_PREFERRED_OWNER]
            winners[code] = min(preferred or group, key=lambda pp: pp.polygon_id).polygon_id
        return winners

    @staticmethod
    def _status_of(pp: PolygonProblem, winners: Dict[str, int]) -> Tuple[str, str]:
        if pp.owner.lower() in _lower_set(settings.POLYGON_SKIP_OWNERS):
            return PolygonProblem.SKIPPED, f'Excluded owner {pp.owner}'
        if pp.tags_error:
            return PolygonProblem.FAILED, f'Tags could not be read, not syncing: {pp.tags_error}'
        skipped = skip_tags_of(pp.tags)
        if skipped:
            return PolygonProblem.SKIPPED, 'Tagged ' + ', '.join(sorted(skipped))
        if winners.get(pp.code) != pp.polygon_id:
            return PolygonProblem.DUPLICATE, f'Code {pp.code} is used by Polygon problem {winners.get(pp.code)}'
        if pp.problem_id is not None:
            if pp.synced_revision == pp.latest_revision:
                return PolygonProblem.SYNCED, ''
            return PolygonProblem.OUTDATED, ''
        if Problem.objects.filter(code=pp.code).exists():
            return PolygonProblem.CONFLICT, f'A problem with code {pp.code} already exists and was not synced from Polygon'
        return PolygonProblem.NEW, ''

    # ---- synchronisation ---------------------------------------------------------------------------------

    @staticmethod
    def sync_author() -> Profile:
        username = settings.POLYGON_SYNC_AUTHOR
        try:
            return Profile.objects.get(user__username=username)
        except Profile.DoesNotExist:
            raise PolygonSyncError(f'POLYGON_SYNC_AUTHOR user {username!r} does not exist')

    def sync_problem(self, pp: PolygonProblem, force: bool = False, author: Optional[Profile] = None) -> PolygonProblem:
        """Sync one problem. Never raises for per-problem failures; they are recorded on the row."""
        author = author or self.sync_author()
        try:
            pp = self.refresh_one(pp)
            if pp.status in (PolygonProblem.SKIPPED, PolygonProblem.DUPLICATE, PolygonProblem.CONFLICT):
                return pp
            if pp.status == PolygonProblem.SYNCED and not force:
                return pp
            self._import(pp, force, author)
        except (PolygonAPIError, PolygonSyncError, ImportPolygonError) as e:
            self._fail(pp, str(e))
        except Exception as e:
            logger.exception('Unexpected error syncing Polygon problem %s', pp.polygon_id)
            self._fail(pp, f'{type(e).__name__}: {e}')
        pp.refresh_from_db()
        return pp

    @staticmethod
    def _fail(pp: PolygonProblem, message: str):
        pp.status = PolygonProblem.FAILED
        pp.message = message[:2000]
        pp.save(update_fields=['status', 'message'])

    def _import(self, pp: PolygonProblem, force: bool, author: Profile):
        package = pick_full_package(self.client.packages(pp.polygon_id))
        if package is None:
            raise PolygonSyncError(
                f'No READY "{FULL_PACKAGE_TYPE}" (full) package. Build a full package on Polygon first.',
            )
        if package['revision'] == pp.synced_revision and pp.problem_id is not None and not force:
            pp.status, pp.message = PolygonProblem.SYNCED, ''
            pp.save(update_fields=['status', 'message'])
            return

        existing = pp.problem
        group, types = map_tags(pp.tags)
        authors, curators = [author], []
        if existing is not None:
            # Updating must not wipe what was curated by hand on MSOJ.
            authors, curators = list(existing.authors.all()), list(existing.curators.all())
            group = group or existing.group
            types = types or list(existing.types.all())
        old_points = existing.points if existing is not None else None

        self.log(f'  downloading {pp.name} (revision {package["revision"]})')
        with self.client.download_package(pp.polygon_id, package['id'], FULL_PACKAGE_TYPE) as file:
            config = statement_config(zipfile.ZipFile(file))
            PolygonImporter(
                package=file,
                code=pp.code,
                authors=authors,
                curators=curators,
                do_update=existing is not None,
                interactive=False,
                config=config,
                group=group,
                types=types,
            ).run()

        problem = Problem.objects.get(code=pp.code)
        if old_points is not None:
            # The importer resets points to a placeholder; keep the value an admin may have chosen.
            Problem.objects.filter(pk=problem.pk).update(points=old_points)
        pp.problem = problem
        pp.synced_revision = package['revision']
        pp.status = PolygonProblem.SYNCED if package['revision'] == pp.latest_revision else PolygonProblem.OUTDATED
        pp.message = ''
        pp.last_synced = timezone.now()
        pp.save()

    def sync_all(self, rows: Optional[Iterable[PolygonProblem]] = None, force: bool = False) -> Dict[str, int]:
        author = self.sync_author()
        rows = list(rows) if rows is not None else list(PolygonProblem.objects.all())
        pending = [
            pp for pp in rows
            if pp.status in (PolygonProblem.NEW, PolygonProblem.OUTDATED, PolygonProblem.FAILED)
            or (force and pp.status == PolygonProblem.SYNCED)
        ]
        self.log(f'{len(pending)} problems to sync')
        counts = defaultdict(int)
        for i, pp in enumerate(pending, start=1):
            result = self.sync_problem(pp, force=force, author=author)
            counts[result.status] += 1
            note = f' - {result.message}' if result.message else ''
            self.log(f'[{i}/{len(pending)}] {result.name}: {result.status}{note}')
        return dict(counts)

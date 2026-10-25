"""Build full Polygon packages sequentially without importing or changing local data."""
import time
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from judge.utils.polygon_api import PolygonAPIError, PolygonClient
from judge.utils.polygon_sync import FULL_PACKAGE_TYPE, skip_tags_of


class Command(BaseCommand):
    help = ('Build missing full packages on Polygon and wait for linux/READY. '
            'Respects sync exclusions; does not import problems.')

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='*', help='Polygon names or IDs (default: all visible problems)')
        parser.add_argument('--dry-run', action='store_true', help='Inspect and print the plan; do not build')
        parser.add_argument('--poll-interval', type=int, default=15, help='Seconds between build checks (default: 15)')
        parser.add_argument('--timeout', type=int, default=1800, help='Build wait limit per problem in seconds (default: 1800)')

    def handle(self, *args, **options):
        if options['poll_interval'] <= 0 or options['timeout'] <= 0:
            raise CommandError('--poll-interval and --timeout must be positive')
        client = PolygonClient()
        counts = Counter()
        try:
            rows = [p for p in client.list_problems() if not p.get('deleted')]
            if options['names']:
                wanted = set(options['names'])
                rows = [p for p in rows if p['name'] in wanted or str(p['id']) in wanted]
                missing = wanted - {p['name'] for p in rows} - {str(p['id']) for p in rows}
                if missing:
                    raise CommandError('Unknown Polygon problem(s): ' + ', '.join(sorted(missing)))
            self.stdout.write(f'{len(rows)} Polygon problems selected')
            for index, problem in enumerate(rows, 1):
                label = f'[{index}/{len(rows)}] {problem["id"]} {problem["owner"]}/{problem["name"]}'
                try:
                    status, detail = self.build_one(client, problem, options)
                except PolygonAPIError as exc:
                    status, detail = 'failed', str(exc)
                counts[status] += 1
                self.stdout.write(f'{label}: {status} - {detail}')
            self.stdout.write('Summary: ' + (', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'no problems'))
            if counts['failed']:
                raise CommandError('Some packages failed or have an unknown outcome; inspect Polygon before rerunning.')
        except PolygonAPIError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            client.session.close()

    def build_one(self, client, problem, options):
        if problem['owner'].lower() in {owner.lower() for owner in settings.POLYGON_SKIP_OWNERS}:
            return 'skipped', 'excluded owner'
        tags = skip_tags_of(client.view_tags(problem['id']))
        if tags:
            return 'skipped', 'excluded tags: ' + ', '.join(sorted(tags))
        revision = problem['revision']
        packages = client.packages(problem['id'])
        current = [p for p in packages if p['revision'] == revision]
        ready = [p for p in current if p['type'] == FULL_PACKAGE_TYPE and p['state'] == 'READY']
        if ready:
            return 'ready', f'linux package already available for revision {revision}'
        active = [p for p in current if p['state'] in ('PENDING', 'RUNNING')]
        if active:
            if options['dry_run']:
                return 'would_wait', f'package build already active for revision {revision}'
            self.stdout.write(f'  Waiting for existing build of {problem["name"]}...')
            self.wait_ready(client, problem, {p['id'] for p in current if p not in active}, options)
            return 'ready', f'existing build produced linux/READY for revision {revision}'
        if problem.get('accessType') not in ('WRITE', 'OWNER'):
            return 'skipped', 'WRITE/OWNER access required'
        if problem.get('modified'):
            raise PolygonAPIError('Uncommitted working-copy changes; commit/review them in Polygon first')
        if options['dry_run']:
            return 'would_build', f'full=true, verify=true, revision {revision}'
        self.stdout.write(f'  Starting full verified build of {problem["name"]}...')
        # A lost response may still have started the build. Never automatically repeat this mutation.
        retries = client.max_retries
        client.max_retries = 1
        try:
            client.call('problem.buildPackage', problemId=problem['id'], full='true', verify='true')
        finally:
            client.max_retries = retries
        self.wait_ready(client, problem, {p['id'] for p in packages}, options)
        return 'built', f'linux/READY confirmed for revision {revision}'

    def wait_ready(self, client, problem, previous_ids, options):
        deadline = time.monotonic() + options['timeout']
        while time.monotonic() < deadline:
            packages = client.packages(problem['id'])
            current = [p for p in packages if p['revision'] == problem['revision']]
            if any(p['type'] == FULL_PACKAGE_TYPE and p['state'] == 'READY' for p in current):
                return
            failed = [p for p in current if p['id'] not in previous_ids and p['state'] == 'FAILED'
                      and p['type'] in ('standard', FULL_PACKAGE_TYPE)]
            if failed:
                raise PolygonAPIError('Package build failed: ' + '; '.join(p.get('comment') or 'no details' for p in failed))
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(options['poll_interval'], remaining))
        raise PolygonAPIError('Timed out waiting for linux/READY; build may still be running on Polygon')

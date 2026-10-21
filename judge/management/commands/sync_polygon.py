from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from judge.models import PolygonProblem
from judge.utils.polygon_api import PolygonAPIError
from judge.utils.polygon_sync import PolygonSync, PolygonSyncError


class Command(BaseCommand):
    help = ('Synchronise problems from Codeforces Polygon '
            '(skips settings.POLYGON_SKIP_TAGS and settings.POLYGON_SKIP_OWNERS)')

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='*', help='Polygon problem names or ids to sync (default: all)')
        parser.add_argument('--list', action='store_true', help='refresh the index and print it; import nothing')
        parser.add_argument('--refresh-tags', action='store_true', help='re-fetch tags of every problem')
        parser.add_argument('--force', action='store_true', help='re-import problems already at the latest revision')
        parser.add_argument('--no-refresh', action='store_true', help='use the stored index, do not call Polygon list')

    def handle(self, *args, **options):
        translation.activate('en')
        sync = PolygonSync(log=self.stdout.write)

        try:
            if options['no_refresh']:
                rows = list(PolygonProblem.objects.all())
            else:
                rows = sync.refresh_index(refresh_tags=options['refresh_tags'])

            if options['names']:
                wanted = set(options['names'])
                selected = [pp for pp in rows if pp.name in wanted or str(pp.polygon_id) in wanted]
                missing = wanted - {pp.name for pp in selected} - {str(pp.polygon_id) for pp in selected}
                if missing:
                    raise CommandError('Unknown Polygon problem(s): ' + ', '.join(sorted(missing)))
                rows = selected

            if options['list']:
                self.print_index(rows)
                return

            counts = sync.sync_all(rows, force=options['force'])
        except (PolygonAPIError, PolygonSyncError) as e:
            raise CommandError(e)

        self.stdout.write('Done: ' + (', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'nothing to sync'))

    def print_index(self, rows):
        by_status = {}
        for pp in sorted(rows, key=lambda pp: pp.polygon_id):
            by_status[pp.status] = by_status.get(pp.status, 0) + 1
            rev = f'r{pp.synced_revision or "-"}/r{pp.latest_revision or "-"}'
            note = f'  [{pp.message}]' if pp.message else ''
            self.stdout.write(f'{pp.polygon_id:>8} {pp.status:<9} {rev:<8} {pp.owner:<14} {pp.code}{note}')
        self.stdout.write('Summary: ' + ', '.join(f'{k}={v}' for k, v in sorted(by_status.items())))

"""Create the ProblemType / ProblemGroup / PolygonTagMapping rows used when syncing from Polygon."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mentor.polygon_tag_mapping import PolygonTagMapError, apply_plan, build_plan


class Command(BaseCommand):
    help = (
        'Map Polygon tags to MSOJ problem types/groups named after the roadmap curriculum.\n'
        'Defaults to dry-run. Existing rows are never modified.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='write to the database')

    def handle(self, *args, **options):
        try:
            plan = build_plan()
        except PolygonTagMapError as e:
            raise CommandError(f'Invalid Polygon tag map:\n{e}')

        for entry in plan:
            self.stdout.write(f'{entry["tag"]:<32} -> type {entry["type"][0]:<22} group {entry["group"][0]}')

        if not options['apply']:
            self.stdout.write(f'\nDry run: {len(plan)} tags would be mapped. Re-run with --apply to write.')
            return

        with transaction.atomic():
            created = apply_plan(plan)
        self.stdout.write(self.style.SUCCESS(
            f'\nCreated {len(created["mappings"])} mappings, {len(created["types"])} types, '
            f'{len(created["groups"])} groups ({len(plan) - len(created["mappings"])} mappings already existed).'
        ))

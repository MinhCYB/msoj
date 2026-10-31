"""Django management command to safely seed the approved MSOJ curriculum roadmap."""
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mentor.roadmap_curriculum import (
    DEFAULT_MANIFEST_PATH,
    CurriculumConflictError,
    CurriculumValidationError,
    apply_curriculum_seed,
    load_curriculum_manifest,
    plan_curriculum_seed,
    validate_curriculum_manifest,
)


class Command(BaseCommand):
    help = (
        "Inspect or seed the approved MSOJ Competitive Programming curriculum.\n"
        "Defaults to dry-run (no writes). Writing requires --apply, --user <staff_user>,\n"
        "--isolated-dev, and settings.ROADMAP_CURRICULUM_SEED_ALLOWED=True.\n"
        "Multi-db aliases are not supported (default database only)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Execute database writes. Default is dry-run mode (no writes).',
        )
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Username of the active staff user performing the seeding (required for --apply).',
        )
        parser.add_argument(
            '--isolated-dev',
            action='store_true',
            default=False,
            help=(
                'Explicit opt-in confirming this is an isolated development or testing environment. '
                'Required when using --apply.'
            ),
        )
        parser.add_argument(
            '--database',
            type=str,
            default='default',
            help="Database alias. Only 'default' is supported by roadmap forest locks and services.",
        )
        parser.add_argument(
            '--manifest',
            type=str,
            default=None,
            help=f"Path to custom curriculum manifest JSON (defaults to {DEFAULT_MANIFEST_PATH}).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        database = options.get('database', 'default')
        if database != 'default':
            raise CommandError(
                f"Unsupported database '{database}'. Roadmap forest locks and services are only safe "
                "on the 'default' database."
            )

        apply_mode = options.get('apply', False)
        isolated_dev = options.get('isolated_dev', False)
        username = options.get('user')
        manifest_path = options.get('manifest')

        # Load manifest
        try:
            path = Path(manifest_path) if manifest_path else None
            manifest = load_curriculum_manifest(manifest_path=path)
            validate_curriculum_manifest(manifest)
        except (CurriculumValidationError, FileNotFoundError) as err:
            raise CommandError(f"Curriculum manifest validation failed: {err}") from err

        if not apply_mode:
            self._handle_dry_run(manifest=manifest, database=database)
            return

        # Guards for --apply mode
        if not isolated_dev:
            raise CommandError(
                "Refusing to write to database: --apply requires explicit --isolated-dev opt-in flag."
            )

        if not getattr(settings, 'ROADMAP_CURRICULUM_SEED_ALLOWED', False):
            raise CommandError(
                "Curriculum seeding is disabled: settings.ROADMAP_CURRICULUM_SEED_ALLOWED is False.\n"
                "To prevent accidental writes to production/application databases, seeding is only\n"
                "permitted when ROADMAP_CURRICULUM_SEED_ALLOWED=True is explicitly set in settings."
            )

        if not username:
            raise CommandError("--apply requires an active staff user specified via --user <username>.")

        User = get_user_model()
        try:
            user = User.objects.using(database).get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.")

        if not user.is_active:
            raise CommandError(f"User '{username}' is not active.")

        if not user.is_staff:
            raise CommandError(f"User '{username}' is not a staff member.")

        required_perms = ['mentor.add_roadmap', 'mentor.add_roadmapnode', 'mentor.publish_roadmap']
        missing_perms = [p for p in required_perms if not user.has_perm(p)]
        if missing_perms:
            raise CommandError(
                f"User '{username}' lacks required permissions for seeding: {', '.join(missing_perms)}"
            )

        self._handle_apply(user=user, manifest=manifest, database=database)

    def _handle_dry_run(self, manifest: dict, database: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("=== Curriculum Seed Plan (DRY-RUN, NO WRITES) ==="))
        plan = plan_curriculum_seed(manifest=manifest, database=database)

        self.stdout.write(f"Roadmap: {plan.roadmap_slug} ('{plan.roadmap_title}')")
        self.stdout.write(f"Roadmap action: {plan.roadmap_action.upper()}")

        if plan.conflicts:
            self.stdout.write(self.style.ERROR(f"\nDetected {len(plan.conflicts)} conflict(s):"))
            for conflict in plan.conflicts:
                self.stdout.write(self.style.ERROR(f"  [{conflict.kind}] {conflict.message}"))

        self.stdout.write("\nSummary:")
        self.stdout.write(f"  Nodes planned to create: {len(plan.nodes_to_create)}")
        self.stdout.write(f"  Nodes matched (no-op):   {len(plan.nodes_matched)}")
        self.stdout.write(f"  Conflicts:               {len(plan.conflicts)}")
        self.stdout.write(f"  Unexpected extra nodes:  {len(plan.extra_nodes)}")
        self.stdout.write(
            f"  Seed prerequisites:     {plan.prerequisite_targets_count} targets, "
            f"{plan.prerequisite_edges_count} edges (persisted for newly created nodes)"
        )

        if not plan.is_valid_for_apply:
            raise CommandError(
                f"Dry-run identified {len(plan.conflicts)} conflict(s). Seeding cannot proceed."
            )

        self.stdout.write(self.style.SUCCESS("\nDry-run completed successfully. Database was not modified."))

    def _handle_apply(self, user: Any, manifest: dict, database: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("=== Applying Curriculum Seed ==="))
        try:
            result = apply_curriculum_seed(
                user=user,
                manifest=manifest,
                database=database,
                isolated_dev=True,
            )
        except CurriculumConflictError as err:
            for conflict in err.conflicts:
                self.stdout.write(self.style.ERROR(f"  [{conflict.kind}] {conflict.message}"))
            raise CommandError(f"Seeding failed atomically due to {len(err.conflicts)} conflict(s).") from err

        self.stdout.write(self.style.SUCCESS("\nCurriculum seed completed successfully!"))
        self.stdout.write(f"  Roadmap:                 {result['roadmap_slug']} (created={result['roadmap_created']})")
        self.stdout.write(f"  Nodes created:           {result['nodes_created']}")
        self.stdout.write(f"  Nodes matched (no-op):   {result['nodes_matched']}")
        self.stdout.write(
            f"  Seed prerequisites:     {result['prerequisite_targets_count']} targets, "
            f"{result['prerequisite_edges_count']} edges (database rows)"
        )

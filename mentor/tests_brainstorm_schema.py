from datetime import timedelta
from unittest.mock import Mock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from copy import deepcopy
from uuid import uuid4
from django.db import IntegrityError, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from .tests_roadmap_migrations import RehearsalRouter

from judge.models import Contest, ContestParticipation, Language, Problem, ProblemGroup, Profile

from .admin import BrainstormContestConfigAdmin, BrainstormPolicyVersionAdmin, ProblemHintAdmin
from .models import (BrainstormCall, BrainstormContestConfig, BrainstormMessage, BrainstormPolicy,
                     BrainstormPolicyVersion, BrainstormSession, BrainstormTurn, ProblemHint)


class BrainstormSchemaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('scope-owner')
        self.profile = Profile.objects.create(user=self.user)
        self.group = ProblemGroup.objects.create(name='scope', full_name='Scope')
        self.problem = Problem.objects.create(code='scope_test', name='Scope test', group=self.group,
                                              time_limit=1, memory_limit=65536, points=100, is_public=True)
        self.language = Language.objects.create(key='SCOPE', name='Scope language', common_name='Python',
                                                ace='python', pygments='python', extension='py')

    def contest(self, name, virtual=0):
        contest = Contest.objects.create(key=name, name=name,
                                         start_time=timezone.now() - timedelta(hours=1),
                                         end_time=timezone.now() + timedelta(hours=1))
        return ContestParticipation.objects.create(contest=contest, user=self.profile, virtual=virtual)

    def test_scope_is_unique_and_virtual_participations_are_separate(self):
        practice = BrainstormSession.objects.create(profile=self.profile, problem=self.problem)
        self.assertEqual(practice.scope_key, 'practice')
        with self.assertRaises(IntegrityError), transaction.atomic():
            BrainstormSession.objects.create(profile=self.profile, problem=self.problem)
        first = self.contest('scope-a')
        second = self.contest('scope-b')
        virtual = ContestParticipation.objects.create(contest=first.contest, user=self.profile, virtual=1)
        sessions = [BrainstormSession.objects.create(profile=self.profile, problem=self.problem,
                                                     participation=p, scope_key=f'participation:{p.pk}')
                    for p in (first, second, virtual)]
        self.assertEqual(len({practice.scope_key, *(s.scope_key for s in sessions)}), 4)
        for session in sessions:
            session.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BrainstormSession.objects.create(profile=self.profile, problem=self.problem,
                                             participation=first, scope_key=f'participation:{first.pk}')
        with self.assertRaises(IntegrityError), transaction.atomic():
            BrainstormSession.objects.create(profile=self.profile, problem=self.problem,
                                             scope_key='participation:999')
        with self.assertRaises(IntegrityError), transaction.atomic():
            BrainstormSession.objects.create(profile=self.profile, problem=self.problem,
                                             participation=first, scope_key='practice')
        other = User.objects.create_user('other-scope')
        other_profile = Profile.objects.create(user=other)
        mismatched = BrainstormSession(profile=other_profile, problem=self.problem,
                                       participation=first, scope_key=f'participation:{first.pk}')
        with self.assertRaises(ValidationError):
            mismatched.full_clean()

    def policy_version(self, version=1, **kwargs):
        return BrainstormPolicyVersion.objects.create(version=version, **kwargs)

    def test_policy_defaults_versioned_publication_and_template_validation(self):
        policy = BrainstormPolicy.objects.create()
        self.assertFalse(policy.enabled)
        draft = self.policy_version()
        self.assertEqual((draft.level_2_after_seconds, draft.level_3_after_seconds, draft.idle_timeout_seconds),
                         (600, 1500, 300))
        self.assertEqual((draft.max_active_turns_per_session, draft.max_active_turns_per_profile,
                          draft.max_turns_per_day_per_profile, draft.max_provider_calls_per_day_per_profile,
                           draft.max_application_calls_per_turn, draft.code_retention_hours), (1, 2, 10, 60, 6, 24))
        self.assertEqual((draft.generator_max_tokens, draft.reviewer_max_tokens), (1200, 256))
        draft.generator_max_tokens = 0
        with self.assertRaises(ValidationError):
            draft.full_clean()
        draft.generator_max_tokens = 1200
        draft.reviewer_max_tokens = 0
        with self.assertRaises(ValidationError):
            draft.full_clean()
        draft.reviewer_max_tokens = 256
        policy.enabled = True
        with self.assertRaises(ValidationError):
            policy.full_clean()
        draft.level_2_after_seconds = 1600
        with self.assertRaises(ValidationError):
            draft.full_clean()
        draft.level_2_after_seconds = 600
        draft.general_prompt = 'Tutoring policy'
        draft.level_1_prompt = 'Ask about {{ student_question }}'
        draft.level_2_prompt = 'Hint level 2'
        draft.level_3_prompt = 'Hint level 3'
        draft.reviewer_prompt = 'Review {{ solution }}'
        draft.is_published = True
        draft.save()
        policy.published_version = draft
        policy.full_clean()
        self.assertTrue(draft.is_published)
        self.assertIsNotNone(draft.published_at)
        draft.max_turns_per_day_per_profile = 100
        with self.assertRaises(ValidationError):
            draft.save()
        revision = self.policy_version(2)
        self.assertFalse(revision.is_published)
        bad = BrainstormPolicyVersion(version=3, general_prompt='{{ solution }}')
        bad.is_published = True
        bad.published_at = timezone.now()
        bad.level_1_prompt = bad.level_2_prompt = bad.level_3_prompt = bad.reviewer_prompt = 'ok'
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_turn_messages_and_call_audit(self):
        session = BrainstormSession.objects.create(profile=self.profile, problem=self.problem)
        version = self.policy_version()
        turn = BrainstormTurn.objects.create(session=session, client_request_id='request-1', request_digest='d' * 64,
                                             policy_version=version, hint_level=1, question_snapshot='Why?',
                                             approach_snapshot='Binary search', current_code_snapshot='print(1)',
                                             code_digest='e' * 64, code_length=8,
                                             code_expires_at=timezone.now() + timedelta(hours=24),
                                             language=self.language, reserved_provider_calls=6)
        self.assertEqual(turn.status, 'pending')
        self.assertEqual(turn.current_code_snapshot, 'print(1)')
        with self.assertRaises(IntegrityError), transaction.atomic():
            BrainstormTurn.objects.create(session=session, client_request_id='request-1', request_digest='f' * 64,
                                          policy_version=version, hint_level=1, question_snapshot='Why?',
                                          approach_snapshot='Binary search', code_digest='e' * 64,
                                          code_expires_at=timezone.now(), language=self.language)
        BrainstormMessage.objects.create(session=session, turn=turn, role='student',
                                         described_approach='Binary search', content='Why?')
        BrainstormMessage.objects.create(session=session, turn=turn, role='ai', content='Consider bounds',
                                         hint_level_granted=1)
        self.assertEqual(list(session.messages.values_list('role', flat=True)), ['student', 'ai'])
        self.assertFalse(session.messages.filter(is_legacy_stub=True).exists())
        legacy = BrainstormMessage.objects.create(session=session, role='ai', content='[STUB]')
        self.assertTrue(legacy.is_legacy_stub)
        call = BrainstormCall.objects.create(turn=turn, role='review', ordinal=1, status='succeeded',
                                             provider='test', requested_model='opaque', returned_model='normalized',
                                             input_tokens=11, output_tokens=4, total_tokens=15,
                                             finish_reason='stop', reviewer_reason_code='approved')
        self.assertEqual(call.total_tokens, 15)
        self.assertFalse(any(x in (field.name for field in BrainstormCall._meta.fields)
                             for x in ('prompt', 'draft', 'raw_response', 'authorization')))

    def test_contest_switch_and_ordered_problem_hints(self):
        participation = self.contest('scope-toggle')
        setting = BrainstormContestConfig.objects.create(contest=participation.contest)
        self.assertFalse(setting.enabled)
        ProblemHint.objects.create(problem=self.problem, content='Second', order=2, enabled=True)
        ProblemHint.objects.create(problem=self.problem, content='First', order=1, enabled=True)
        other_problem = Problem.objects.create(code='scope_other', name='Other', group=self.group,
                                               time_limit=1, memory_limit=65536, points=100, is_public=True)
        ProblemHint.objects.create(problem=other_problem, content='Other hint', enabled=True)
        self.assertEqual(list(self.problem.mentor_brainstorm_hints.filter(enabled=True).values_list('content', flat=True)),
                         ['First', 'Second'])

    def test_admin_limits_scoped_edits_and_hides_snapshots(self):
        from django.contrib.auth.models import Permission
        from .admin import BrainstormPolicyAdmin, BrainstormTurnAdmin

        site = AdminSite()
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.user.user_permissions.add(Permission.objects.get(codename='edit_own_problem'),
                                       Permission.objects.get(codename='edit_own_contest'))
        request = Mock(user=self.user, profile=self.profile)
        problem_admin = ProblemHintAdmin(ProblemHint, site)
        contest_admin = BrainstormContestConfigAdmin(BrainstormContestConfig, site)
        other = User.objects.create_user('hint-other', is_staff=True)
        other_profile = Profile.objects.create(user=other)
        other.user_permissions.add(Permission.objects.get(codename='edit_own_problem'),
                                   Permission.objects.get(codename='edit_own_contest'))
        self.problem.authors.add(self.profile)
        hint = ProblemHint.objects.create(problem=self.problem, content='Try invariants')
        self.assertTrue(problem_admin.has_change_permission(request, hint))
        self.assertFalse(problem_admin.has_change_permission(Mock(user=other, profile=other_profile), hint))
        self.assertNotIn(hint, problem_admin.get_queryset(Mock(user=other, profile=other_profile)))
        contest = self.contest('hint-contest').contest
        contest.authors.add(self.profile)
        config = BrainstormContestConfig.objects.create(contest=contest)
        self.assertTrue(contest_admin.has_change_permission(request, config))
        self.assertFalse(contest_admin.has_change_permission(Mock(user=other, profile=other_profile), config))
        self.assertFalse(BrainstormPolicyAdmin(BrainstormPolicy, site).has_view_permission(request))
        turn_admin = BrainstormTurnAdmin(BrainstormTurn, site)
        self.assertFalse(turn_admin.has_add_permission(request))
        self.assertFalse(turn_admin.has_change_permission(request))
        self.assertNotIn('current_code_snapshot', turn_admin.get_readonly_fields(request))
        self.assertIn('current_code_snapshot', turn_admin.exclude)


class BrainstormMigrationTests(TransactionTestCase):
    """Exercise backfill on an actual pre-3A database, including legacy STUB rows."""
    databases = {'default'}

    def setUp(self):
        super().setUp()
        default = connections['default']
        if default.vendor != 'mysql':
            self.skipTest('Migration rehearsal uses the deployment-compatible MySQL backend.')
        self.database_name = 'test_brainstorm_mig_' + uuid4().hex[:12]
        self.alias = 'brainstorm_migration'
        config = deepcopy(default.settings_dict)
        config['NAME'] = self.database_name
        config['TEST']['MIRROR'] = None
        with default.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{self.database_name}` CHARACTER SET utf8mb4')
        connections.databases[self.alias] = config
        self.db = connections[self.alias]
        self.addCleanup(self.cleanup_database)
        self.old = [('mentor', '0003_review_provider_call_started_at')]
        self.new = [('mentor', '0004_brainstormcall_brainstormcontestconfig_and_more')]
        executor = MigrationExecutor(self.db)
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter(self.alias)]):
            executor.migrate(self.old)
        self.old_apps = executor.loader.project_state(self.old).apps

    def cleanup_database(self):
        self.db.close()
        del connections[self.alias]
        del connections.databases[self.alias]
        with connections['default'].cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{self.database_name}`')

    def test_backfill_preserves_messages_as_unapproved(self):
        with override_settings(DATABASE_ROUTERS=[RehearsalRouter(self.alias)]):
            apps = self.old_apps
            UserModel = apps.get_model('auth', 'User')
            ProfileModel = apps.get_model('judge', 'Profile')
            GroupModel = apps.get_model('judge', 'ProblemGroup')
            ProblemModel = apps.get_model('judge', 'Problem')
            SessionModel = apps.get_model('mentor', 'BrainstormSession')
            MessageModel = apps.get_model('mentor', 'BrainstormMessage')
            user = UserModel.objects.using(self.alias).create(username='migration-scope-owner')
            profile = ProfileModel.objects.using(self.alias).create(user=user)
            group = GroupModel.objects.using(self.alias).create(name='migration-scope', full_name='Migration scope')
            problem = ProblemModel.objects.using(self.alias).create(code='MIG_SCOPE', name='Migration scope', group=group,
                                                                  time_limit=1, memory_limit=65536, points=100)
            session = SessionModel.objects.using(self.alias).create(profile=profile, problem=problem)
            message = MessageModel.objects.using(self.alias).create(session=session, role='ai', content='[STUB] old response',
                                                                  hint_level_granted=1)
            executor = MigrationExecutor(self.db)
            executor.migrate(self.new)
            apps = executor.loader.project_state(self.new).apps
            updated = apps.get_model('mentor', 'BrainstormSession').objects.using(self.alias).get(pk=session.pk)
            migrated = apps.get_model('mentor', 'BrainstormMessage').objects.using(self.alias).get(pk=message.pk)
            self.assertEqual(updated.scope_key, 'practice')
            self.assertIsNone(updated.participation_id)
            self.assertEqual(migrated.content, '[STUB] old response')
            self.assertTrue(migrated.is_legacy_stub)
            self.assertIsNone(migrated.turn_id)
            with self.db.cursor() as cursor:
                self.assertIn('provider_call_started_at',
                              [column.name for column in self.db.introspection.get_table_description(
                                  cursor, 'mentor_aireviewattempt')])

from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Thread

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from billing.constants import FEATURE_AI_BRAINSTORM
from billing.models import Plan, Subscription
from judge.models import (Contest, ContestParticipation, ContestProblem, Language, Problem,
                          ProblemGroup, Profile, Solution)

from .brainstorm_context import BrainstormContextBuilder, reviewer_reference
from .brainstorm_service import (BrainstormDenied, claim_turn, clear_expired_snapshots,
                                 clear_sensitive_snapshot, finish_turn, resolve_scope, start_reserved_call)
from .models import (BrainstormCall, BrainstormContestConfig, BrainstormMessage, BrainstormPolicy,
                     BrainstormPolicyVersion, BrainstormSession, BrainstormTurn, ProblemHint)


class BrainstormFixture:
    def setUp(self):
        self.user = User.objects.create_user('brainstorm-claim')
        self.profile = Profile.objects.create(user=self.user)
        self.group = ProblemGroup.objects.create(name='brainstorm-claim', full_name='Brainstorm claim')
        self.problem = self.problem_factory('claim_problem')
        self.language = Language.objects.create(key='CLAIM', name='Claim', common_name='Claim',
                                                ace='python', pygments='python', extension='py')
        self.problem.allowed_languages.add(self.language)
        self.version = BrainstormPolicyVersion.objects.create(
            version=1, is_published=True, general_prompt='Policy', level_1_prompt='One',
            level_2_prompt='Two', level_3_prompt='Three', reviewer_prompt='Review {{ solution }}')
        self.switch = BrainstormPolicy.objects.create(enabled=True, published_version=self.version)
        self.plan = Plan.objects.create(name='Claim plan', scope=Plan.SCOPE_PERSONAL,
                                        pricing_type=Plan.PRICING_PER_DAY, price_per_day=Decimal('1.00'),
                                        features=[FEATURE_AI_BRAINSTORM])
        Subscription.objects.create(profile=self.profile, plan=self.plan, status=Subscription.STATUS_ACTIVE,
                                    start_date=timezone.now()-timedelta(days=1),
                                    end_date=timezone.now()+timedelta(days=1), price_paid=Decimal('1.00'))

    def problem_factory(self, code):
        return Problem.objects.create(code=code, name=code, description='Solve the task.', group=self.group,
                                      time_limit=1, memory_limit=65536, points=100, is_public=True)

    def payload(self, key='turn-1', **changes):
        return {'question': 'How do I start?', 'approach': 'Try sorting.', 'current_code': 'print(1)',
                'language_key': self.language.key, 'client_request_id': key, **changes}

    def claim(self, key='turn-1', *, problem=None, now=None, **changes):
        return claim_turn(self.profile, problem or self.problem, self.payload(key, **changes), now=now)

    def denied(self, code, key='turn-1', *, problem=None, **changes):
        with self.assertRaises(BrainstormDenied) as result:
            self.claim(key, problem=problem, **changes)
        self.assertEqual(result.exception.code, code)

    def contest(self, key, *, virtual=0, ended=False, problem=None):
        now = timezone.now()
        contest = Contest.objects.create(key=key, name=key, is_visible=True, start_time=now-timedelta(hours=2),
                                         end_time=now+timedelta(hours=2))
        participation = ContestParticipation.objects.create(contest=contest, user=self.profile, virtual=virtual,
                                                             real_start=now-timedelta(hours=2) if ended else now)
        ContestProblem.objects.create(contest=contest, problem=problem or self.problem, order=1, points=100)
        BrainstormContestConfig.objects.create(contest=contest, enabled=True)
        self.profile.current_contest = participation
        self.profile.save(update_fields=['current_contest'])
        return participation


class BrainstormClaimTests(BrainstormFixture, TestCase):
    def test_claim_duplicate_digest_and_safe_snapshot(self):
        turn, context, created = self.claim()
        self.assertTrue(created)
        self.assertEqual((turn.status, turn.hint_level, turn.reserved_provider_calls), ('pending', 1, 6))
        self.assertEqual(context.current['code'], 'print(1)')
        self.assertEqual(BrainstormMessage.objects.count(), 0)
        session = turn.session
        original_time = session.last_activity_at
        same, _, created = self.claim()
        self.assertFalse(created)
        self.assertEqual(same.pk, turn.pk)
        session.refresh_from_db()
        self.assertEqual(session.last_activity_at, original_time)
        self.assertEqual((session.total_active_seconds, session.turns.count()), (0, 1))
        self.denied('idempotency_conflict', question='Different')
        self.denied('turn_in_progress', 'another')
        self.assertEqual(session.turns.count(), 1)
        clear_sensitive_snapshot(turn)
        turn.refresh_from_db()
        self.assertEqual(turn.current_code_snapshot, '')
        self.assertEqual(turn.code_length, 8)

    def test_guards_and_invalid_input_precede_reservation(self):
        self.switch.enabled = False
        self.switch.save()
        self.denied('brainstorm_disabled')
        self.switch.enabled = True
        self.switch.save()
        Subscription.objects.filter(profile=self.profile).update(status='expired')
        self.denied('subscription_required')
        Subscription.objects.filter(profile=self.profile).update(status=Subscription.STATUS_ACTIVE)
        self.denied('invalid_question', question='  ')
        self.denied('invalid_question', key='bad key')
        self.denied('payload_too_large', question='x' * (self.version.max_question_chars + 1))
        self.denied('unsupported_language', language_key='UNKNOWN')
        self.language.file_only = True
        self.language.save(update_fields=['file_only'])
        self.denied('unsupported_language')
        self.language.file_only = False
        self.language.save(update_fields=['file_only'])
        self.problem.description = ''
        self.problem.save(update_fields=['description'])
        self.denied('unsupported_problem')
        self.assertFalse(BrainstormTurn.objects.exists())
        self.assertFalse(BrainstormSession.objects.exists())

    def test_server_scopes_contests_virtual_and_ended(self):
        self.assertEqual(resolve_scope(self.profile, self.problem).key, 'practice')
        first = self.contest('claim-a')
        turn, _, _ = self.claim()
        self.assertEqual(turn.session.scope_key, f'participation:{first.pk}')
        self.assertEqual(turn.session.participation_id, first.pk)
        other = self.problem_factory('not_in_contest')
        other.allowed_languages.add(self.language)
        self.denied('problem_not_accessible', 'other', problem=other)
        BrainstormContestConfig.objects.filter(contest=first.contest).update(enabled=False)
        self.denied('contest_brainstorm_disabled', 'other')
        BrainstormContestConfig.objects.filter(contest=first.contest).update(enabled=True)
        self.profile.current_contest = None
        self.profile.save(update_fields=['current_contest'])
        practice, _, _ = self.claim('practice')
        self.assertEqual(practice.session.scope_key, 'practice')
        second = self.contest('claim-b', virtual=1)
        self.profile.current_contest = second
        self.profile.save(update_fields=['current_contest'])
        # Profile has two active turns already; a terminal turn releases its slot.
        turn.status = BrainstormTurn.STATUS_SUCCEEDED
        turn.save(update_fields=['status'])
        virtual, _, _ = self.claim('virtual')
        self.assertNotEqual(virtual.session_id, turn.session_id)
        self.assertNotEqual(virtual.session_id, practice.session_id)
        second.real_start = timezone.now()-timedelta(hours=6)
        second.save(update_fields=['real_start'])
        self.denied('contest_scope_ended', 'ended')
        first.contest.end_time = timezone.now()-timedelta(minutes=1)
        first.contest.save(update_fields=['end_time'])
        self.profile.current_contest = first
        self.profile.save(update_fields=['current_contest'])
        self.denied('contest_scope_ended', 'ended-regular')
        self.profile.current_contest = None
        self.profile.save(update_fields=['current_contest'])
        self.assertEqual(resolve_scope(self.profile, self.problem).key, 'practice')

    def test_wrong_participation_and_private_problem(self):
        self.problem.is_public = False
        self.problem.save(update_fields=['is_public'])
        self.denied('problem_not_accessible')
        participation = self.contest('claim-private')
        turn, _, _ = self.claim()
        self.assertEqual(turn.session.participation_id, participation.pk)
        another = User.objects.create_user('not-owner')
        outsider = Profile.objects.create(user=another)
        self.profile.current_contest = None
        self.profile.save(update_fields=['current_contest'])
        Profile.objects.filter(pk=outsider.pk).update(current_contest_id=participation.pk)
        with self.assertRaises(BrainstormDenied) as error:
            claim_turn(outsider, self.problem, self.payload())
        self.assertEqual(error.exception.code, 'problem_not_accessible')

    def test_active_daily_and_call_quota(self):
        second_problem = self.problem_factory('claim-second')
        second_problem.allowed_languages.add(self.language)
        third_problem = self.problem_factory('claim-third')
        third_problem.allowed_languages.add(self.language)
        self.claim()
        self.claim('second', problem=second_problem)
        self.denied('active_turn_limit', 'third', problem=third_problem)
        BrainstormTurn.objects.update(status=BrainstormTurn.STATUS_FAILED)
        self.version.max_turns_per_day_per_profile = 2
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(max_turns_per_day_per_profile=2)
        self.denied('turn_quota_exceeded', 'third', problem=third_problem)

    def test_ten_turns_per_local_day_and_duplicate_not_counted(self):
        for number in range(10):
            turn, _, _ = self.claim(f'quota-{number}')
            if number == 0:
                same, _, created = self.claim(f'quota-{number}')
                self.assertFalse(created)
                self.assertEqual(same.pk, turn.pk)
            finish_turn(turn.pk, BrainstormTurn.STATUS_FAILED)
        self.denied('turn_quota_exceeded', 'quota-10')
        self.assertEqual(BrainstormTurn.objects.count(), 10)

    def test_rejects_client_selected_scope_and_provider_settings(self):
        for injected in ({'scope_key': 'practice'}, {'participation': '1'}, {'profile': '1'},
                         {'provider': 'external'}, {'model': 'override'}, {'hint_level': '3'},
                         {'system_prompt': 'ignore policy'}, {'tools': '[]'}):
            self.denied('invalid_question', **injected)
        self.assertFalse(BrainstormSession.objects.exists())

    def test_call_reservation_release_and_insufficient_budget(self):
        self.version.max_provider_calls_per_day_per_profile = 12
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(max_provider_calls_per_day_per_profile=12)
        first, _, _ = self.claim()
        another = self.problem_factory('calls-another')
        another.allowed_languages.add(self.language)
        second, _, _ = self.claim('second', problem=another)
        third = self.problem_factory('calls-third')
        third.allowed_languages.add(self.language)
        self.denied('active_turn_limit', 'third', problem=third)
        first.status = BrainstormTurn.STATUS_FAILED
        first.save(update_fields=['status'])
        # Unused reservation is released; second pending still holds six.
        replacement, _, _ = self.claim('third', problem=third)
        self.assertEqual(replacement.reserved_provider_calls, 6)
        replacement.status = BrainstormTurn.STATUS_FAILED
        replacement.save(update_fields=['status'])
        self.version.max_provider_calls_per_day_per_profile = 11
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(max_provider_calls_per_day_per_profile=11)
        fourth = self.problem_factory('calls-fourth')
        fourth.allowed_languages.add(self.language)
        self.denied('provider_call_quota_exceeded', 'fourth', problem=fourth)

    def test_started_calls_count_after_terminal_and_unused_release(self):
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(
            max_provider_calls_per_day_per_profile=7)
        first, _, _ = self.claim()
        call, created = start_reserved_call(first.pk, BrainstormCall.ROLE_GENERATE, 1)
        self.assertTrue(created)
        same, created = start_reserved_call(first.pk, BrainstormCall.ROLE_GENERATE, 1)
        self.assertFalse(created)
        self.assertEqual(call.pk, same.pk)
        first.refresh_from_db()
        self.assertEqual(first.used_provider_calls, 1)
        finish_turn(first.pk, BrainstormTurn.STATUS_FAILED)
        first.refresh_from_db()
        self.assertEqual(first.current_code_snapshot, '')
        second = self.problem_factory('call-started')
        second.allowed_languages.add(self.language)
        self.claim('new', problem=second)  # 1 started + 6 reserved = 7.
        third = self.problem_factory('call-exhausted')
        third.allowed_languages.add(self.language)
        self.denied('provider_call_quota_exceeded', 'newer', problem=third)

    def test_sixty_call_reservations_and_next_day_boundary(self):
        base = timezone.now()
        for number in range(10):
            turn, _, _ = self.claim(f'reserve-{number}', now=base)
            for ordinal in range(1, 7):
                start_reserved_call(turn.pk, BrainstormCall.ROLE_GENERATE, ordinal, now=base)
            finish_turn(turn.pk, BrainstormTurn.STATUS_FAILED, now=base)
        other = self.problem_factory('reserve-next')
        other.allowed_languages.add(self.language)
        self.denied('turn_quota_exceeded', 'reserve-11', problem=other)
        # Keep turn quota higher to isolate the provider-call boundary.
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(max_turns_per_day_per_profile=11)
        self.denied('provider_call_quota_exceeded', 'reserve-11', problem=other)

    def test_policy_rotation_preserves_idempotency_and_thresholds(self):
        first, _, _ = self.claim()
        replacement = BrainstormPolicyVersion.objects.create(
            version=2, is_published=True, general_prompt='New policy', level_1_prompt='One',
            level_2_prompt='Two', level_3_prompt='Three', reviewer_prompt='Review {{ solution }}',
            level_2_after_seconds=300)
        self.switch.published_version = replacement
        self.switch.save()
        same, _, created = self.claim()
        self.assertFalse(created)
        self.assertEqual(same.pk, first.pk)
        self.assertEqual(same.policy_version_id, self.version.pk)
        self.denied('idempotency_conflict', current_code='different')
        finish_turn(first.pk, BrainstormTurn.STATUS_FAILED)
        later, _, _ = self.claim('later')
        self.assertEqual(later.policy_version_id, replacement.pk)

    def test_hint_boundaries_idle_cap_duplicate_and_policy_snapshot(self):
        base = timezone.now()
        first, _, _ = self.claim(now=base)
        self.assertEqual(first.hint_level, 1)
        session = first.session
        for key, seconds, expected in [('before', 599, 1), ('exact', 600, 2),
                                       ('after', 1500, 3)]:
            BrainstormTurn.objects.filter(session=session, status='pending').update(status='succeeded')
            BrainstormSession.objects.filter(pk=session.pk).update(total_active_seconds=seconds,
                                                                    last_activity_at=base)
            turn, _, _ = self.claim(key, now=base)
            self.assertEqual(turn.hint_level, expected)
        BrainstormTurn.objects.filter(session=session, status='pending').update(status='succeeded')
        BrainstormSession.objects.filter(pk=session.pk).update(total_active_seconds=100,
                                                                last_activity_at=base-timedelta(hours=1))
        capped, _, _ = self.claim('capped', now=base)
        self.assertEqual(capped.hint_level, 1)
        session.refresh_from_db()
        self.assertEqual(session.total_active_seconds, 400)
        self.claim('capped', now=base+timedelta(seconds=10))
        session.refresh_from_db()
        self.assertEqual(session.total_active_seconds, 400)
        self.assertEqual(capped.policy_version_id, first.policy_version_id)

    def test_hint_elapsed_crosses_both_boundaries(self):
        now = timezone.now()
        first, _, _ = self.claim(now=now)
        finish_turn(first.pk, BrainstormTurn.STATUS_FAILED)
        BrainstormSession.objects.filter(pk=first.session_id).update(
            total_active_seconds=599, last_activity_at=now-timedelta(seconds=1))
        second, _, _ = self.claim('level-two', now=now)
        self.assertEqual(second.hint_level, 2)
        finish_turn(second.pk, BrainstormTurn.STATUS_FAILED)
        BrainstormSession.objects.filter(pk=first.session_id).update(
            total_active_seconds=1499, last_activity_at=now-timedelta(seconds=1))
        third, _, _ = self.claim('level-three', now=now)
        self.assertEqual(third.hint_level, 3)

    def test_first_claim_on_legacy_session_resets_old_stub_timer(self):
        session = BrainstormSession.objects.create(profile=self.profile, problem=self.problem,
                                                   total_active_seconds=1900,
                                                   last_activity_at=timezone.now()-timedelta(hours=2))
        turn, _, _ = self.claim()
        session.refresh_from_db()
        self.assertEqual(turn.hint_level, 1)
        self.assertEqual(session.total_active_seconds, 0)

    def test_approved_pairs_isolation_editorial_budget_and_legacy(self):
        Solution.objects.create(problem=self.problem, content='SECRET EDITORIAL', is_public=False,
                                publish_on=timezone.now()+timedelta(days=1))
        ProblemHint.objects.create(problem=self.problem, content='Hint A', enabled=True, order=1)
        ProblemHint.objects.create(problem=self.problem, content='Disabled', enabled=False, order=2)
        ProblemHint.objects.create(problem=self.problem, content='Hint B', enabled=True, order=3)
        turn, context, _ = self.claim()
        self.assertIn('Solve the task.', context.problem['statement'])
        self.assertEqual(context.hints, ('Hint A',))
        self.assertNotIn('editorial', context.problem)
        self.assertEqual(reviewer_reference(self.problem)['editorial'], 'SECRET EDITORIAL')
        turn.status = BrainstormTurn.STATUS_SUCCEEDED
        turn.save(update_fields=['status'])
        BrainstormMessage.objects.create(session=turn.session, turn=turn, role='student',
                                         content='Approved question', described_approach='Approach')
        BrainstormMessage.objects.create(session=turn.session, turn=turn, role='ai', content='Approved answer' * 7,
                                         hint_level_granted=1)
        BrainstormMessage.objects.create(session=turn.session, role='ai', content='[STUB] FAKE')
        BrainstormMessage.objects.create(session=turn.session, role='student', content='legacy question',
                                         described_approach='legacy approach')
        new, context, _ = self.claim('next', current_code='')
        self.assertEqual(context.current['code'], '')
        self.assertEqual(len(context.history), 1)
        self.assertEqual(context.history[0]['answer'], 'Approved answer' * 7)
        self.assertNotIn('SECRET', str(context))
        self.assertNotIn('FAKE', str(context))
        other = self.problem_factory('history-other')
        other.allowed_languages.add(self.language)
        other_turn, other_context, _ = self.claim('other', problem=other)
        self.assertEqual(other_context.history, ())
        self.assertNotEqual(new.session_id, other_turn.session_id)
        self.version.max_question_chars = 21
        self.version.max_approach_chars = 12
        self.version.max_code_chars = 105
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(
            max_question_chars=21, max_approach_chars=12, max_code_chars=105)
        other_turn.status = BrainstormTurn.STATUS_SUCCEEDED
        other_turn.save(update_fields=['status'])
        # A later request drops oldest complete pairs without splitting them.
        new.status = BrainstormTurn.STATUS_SUCCEEDED
        new.save(update_fields=['status'])
        recent, truncated, _ = self.claim('budget', current_code='')
        self.assertTrue(truncated.history_truncated)
        self.assertEqual(truncated.history, ())
        self.assertTrue(recent.history_truncated)

    def test_expired_code_sweep(self):
        turn, _, _ = self.claim()
        BrainstormTurn.objects.filter(pk=turn.pk).update(code_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(clear_expired_snapshots(), 1)
        turn.refresh_from_db()
        self.assertEqual(turn.current_code_snapshot, '')
        self.assertEqual(clear_expired_snapshots(), 0)

    def test_context_stays_with_session_and_hints_follow_level(self):
        ProblemHint.objects.create(problem=self.problem, content='First hint', enabled=True, order=1)
        ProblemHint.objects.create(problem=self.problem, content='Second hint', enabled=True, order=2)
        ProblemHint.objects.create(problem=self.problem, content='Hidden', enabled=False, order=0)
        initial, _, _ = self.claim()
        finish_turn(initial.pk, BrainstormTurn.STATUS_SUCCEEDED)
        BrainstormMessage.objects.create(session=initial.session, turn=initial, role='student',
                                         content='Private question', described_approach='Try sorting')
        BrainstormMessage.objects.create(session=initial.session, turn=initial, role='ai',
                                         content='Approved response', hint_level_granted=1)
        other_user = User.objects.create_user('other-learner')
        other_profile = Profile.objects.create(user=other_user)
        Subscription.objects.create(profile=other_profile, plan=self.plan, status=Subscription.STATUS_ACTIVE,
                                    start_date=timezone.now()-timedelta(days=1),
                                    end_date=timezone.now()+timedelta(days=1), price_paid=Decimal('1.00'))
        other_turn, other_context, _ = claim_turn(other_profile, self.problem, self.payload('other'))
        self.assertEqual(other_context.history, ())
        self.assertNotEqual(initial.session_id, other_turn.session_id)
        contest = self.contest('context-isolation')
        scoped, contest_context, _ = self.claim('contest')
        self.assertEqual(scoped.session.participation_id, contest.pk)
        self.assertEqual(contest_context.history, ())
        finish_turn(scoped.pk, BrainstormTurn.STATUS_FAILED)
        self.profile.current_contest = None
        self.profile.save(update_fields=['current_contest'])
        BrainstormSession.objects.filter(pk=initial.session_id).update(total_active_seconds=600)
        next_turn, practice_context, _ = self.claim('practice')
        self.assertEqual(next_turn.hint_level, 2)
        self.assertEqual(practice_context.hints, ('First hint', 'Second hint'))
        self.assertEqual(len(practice_context.history), 1)
        self.assertEqual(practice_context.history[0]['answer'], 'Approved response')


class BrainstormConcurrencyTests(BrainstormFixture, TransactionTestCase):
    def test_concurrent_profile_limit_and_same_session(self):
        other = self.problem_factory('concurrent-other')
        other.allowed_languages.add(self.language)
        self.version.max_active_turns_per_profile = 1
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(max_active_turns_per_profile=1)
        barrier = Barrier(2)
        results = []

        def run(problem, key):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                turn, _, _ = self.claim(key, problem=problem)
                results.append(('ok', turn.pk))
            except BrainstormDenied as exc:
                results.append(('denied', exc.code))
            finally:
                close_old_connections()

        threads = [Thread(target=run, args=(p, key)) for p, key in
                   [(self.problem, 'concurrent-one'), (other, 'concurrent-two')]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(kind == 'ok' for kind, _ in results), 1)
        self.assertEqual(BrainstormTurn.objects.filter(status='pending').count(), 1)

    def test_concurrent_same_session_idempotency_and_conflict(self):
        barrier = Barrier(2)
        results = []

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                turn, _, created = self.claim('same-key')
                results.append((turn.pk, created))
            finally:
                close_old_connections()

        threads = [Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len(results), 2)
        self.assertEqual({pk for pk, _ in results}, {BrainstormTurn.objects.get().pk})
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(BrainstormSession.objects.get().total_active_seconds, 0)

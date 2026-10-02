import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ai_gateway.errors import TimeoutError as GatewayTimeout
from ai_gateway.types import GatewayResult, Usage
from judge.models import Profile, Solution

from .brainstorm_pipeline import parse_review, run_brainstorm
from .brainstorm_service import finish_turn
from .models import (BrainstormCall, BrainstormContestConfig, BrainstormMessage, BrainstormPolicyVersion,
                     BrainstormSession, BrainstormTurn)
from .tests_brainstorm_service import BrainstormFixture


def result(text, **kwargs):
    return GatewayResult(text=text, provider='fake', requested_model='opaque', returned_model='normalized',
                         finish_reason='stop', usage=Usage(10, 5, 15), **kwargs)


def verdict(decision, reason):
    return result(json.dumps({'decision': decision, 'reason_code': reason}))


class BrainstormPipelineTests(BrainstormFixture, TestCase):
    def setUp(self):
        super().setUp()
        Solution.objects.create(problem=self.problem, content='PRIVATE EDITORIAL', is_public=False,
                                publish_on=timezone.now()+timedelta(days=1))

    def generate(self, responses):
        turn, _, _ = self.claim()
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=responses) as gateway:
            run_brainstorm(turn.pk)
        turn.refresh_from_db()
        return turn, gateway

    def test_approve_first_two_calls_and_duplicate_delivery(self):
        turn, gateway = self.generate([result('Approved hint'), verdict('approve', 'approved')])
        self.assertEqual(turn.status, 'succeeded')
        self.assertEqual(turn.used_provider_calls, 2)
        self.assertEqual(turn.current_code_snapshot, '')
        self.assertEqual(turn.code_length, 8)
        self.assertEqual([c.role for c in turn.calls.order_by('pk')], ['generate', 'review'])
        self.assertEqual([c.status for c in turn.calls.order_by('pk')], ['succeeded', 'succeeded'])
        self.assertEqual(turn.calls.first().total_tokens, 15)
        self.assertEqual(turn.calls.last().reviewer_reason_code, 'approved')
        self.assertEqual([c.kwargs['role'] for c in gateway.call_args_list],
                         ['brainstorm_generate', 'brainstorm_review'])
        self.assertEqual([c.kwargs['max_tokens'] for c in gateway.call_args_list], [1200, 256])
        generator = str(gateway.call_args_list[0].kwargs['messages'])
        reviewer = str(gateway.call_args_list[1].kwargs['messages'])
        self.assertNotIn('PRIVATE EDITORIAL', generator)
        self.assertIn('PRIVATE EDITORIAL', reviewer)
        messages = list(turn.published_messages.order_by('pk'))
        self.assertEqual([m.role for m in messages], ['student', 'ai'])
        self.assertEqual(messages[0].content, 'How do I start?')
        self.assertEqual(messages[0].described_approach, 'Try sorting.')
        self.assertEqual(messages[1].content, 'Approved hint')
        self.assertTrue(all(not m.is_legacy_stub for m in messages))
        self.assertNotIn('print(1)', str([m.content for m in messages]))
        self.assertNotIn('PRIVATE EDITORIAL', str([m.content for m in messages]))
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate') as unused:
            run_brainstorm(turn.pk)
        unused.assert_not_called()
        self.assertEqual(BrainstormMessage.objects.count(), 2)

    def test_rewrites_bounded_and_only_final_approved_published(self):
        for rejects, expected_calls in ((1, 4), (2, 6), (3, 6)):
            with self.subTest(rejects=rejects):
                responses = []
                for index in range(rejects):
                    responses += [result('Rejected draft %s' % index), verdict('reject', 'hint_level_violation')]
                if rejects < 3:
                    responses += [result('Approved draft'), verdict('approve', 'approved')]
                turn, gateway = self.generate(responses)
                self.assertEqual(gateway.call_count, expected_calls)
                self.assertEqual([c.kwargs['max_tokens'] for c in gateway.call_args_list],
                                 [1200, 256] * (expected_calls // 2))
                self.assertEqual(turn.used_provider_calls, expected_calls)
                self.assertEqual(turn.current_code_snapshot, '')
                self.assertEqual(turn.status, 'failed' if rejects == 3 else 'succeeded')
                self.assertEqual(turn.error_code, 'review_rejected' if rejects == 3 else '')
                self.assertNotIn('Rejected draft', str(list(turn.published_messages.values_list('content', flat=True))))
                self.assertEqual(turn.published_messages.count(), 0 if rejects == 3 else 2)
                self.assertEqual(turn.calls.count(), expected_calls)
                if rejects != 3:
                    self.assertEqual(turn.published_messages.get(role='ai').content, 'Approved draft')
                BrainstormMessage.objects.all().delete()
                BrainstormTurn.objects.all().delete()
                BrainstormSession.objects.all().delete()

    def test_claimed_policy_version_controls_token_caps_after_new_publication(self):
        self.version.generator_max_tokens = 1100
        self.version.reviewer_max_tokens = 210
        BrainstormPolicyVersion.objects.filter(pk=self.version.pk).update(
            generator_max_tokens=1100, reviewer_max_tokens=210)
        turn, _, _ = self.claim()
        replacement = BrainstormPolicyVersion.objects.create(
            version=2, is_published=True, general_prompt='Policy', level_1_prompt='One',
            level_2_prompt='Two', level_3_prompt='Three', reviewer_prompt='Review',
            generator_max_tokens=900, reviewer_max_tokens=128)
        self.switch.published_version = replacement
        self.switch.save(update_fields=['published_version'])
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=[
                result('draft'), verdict('approve', 'approved')]) as gateway:
            run_brainstorm(turn.pk)
        self.assertEqual([c.kwargs['max_tokens'] for c in gateway.call_args_list], [1100, 210])
        turn.refresh_from_db()
        self.assertEqual(turn.status, 'succeeded')
        self.assertEqual(turn.policy_version_id, self.version.pk)

    def test_invalid_generator_and_reviewer_fail_closed(self):
        scenarios = [([result('')], 'generator_invalid_output', 1),
                     ([result('x', tool_calls=[{'id': 'x'}])], 'generator_invalid_output', 1),
                     ([result('draft'), result('not json')], 'reviewer_invalid_output', 2),
                     ([result('draft'), verdict('approve', 'solution_leak')], 'reviewer_invalid_output', 2),
                     ([result('draft'), verdict('reject', 'unknown')], 'reviewer_invalid_output', 2),
                     ([GatewayTimeout('internal timeout')], 'timeout', 1),
                     ([result('draft'), GatewayTimeout('internal timeout')], 'timeout', 2)]
        for responses, expected, count in scenarios:
            with self.subTest(error=expected, count=count):
                turn, gateway = self.generate(responses)
                self.assertEqual(gateway.call_count, count)
                self.assertEqual(turn.error_code, expected)
                self.assertEqual(turn.status, 'failed')
                self.assertEqual(turn.used_provider_calls, count)
                self.assertEqual(turn.current_code_snapshot, '')
                self.assertEqual(turn.published_messages.count(), 0)
                self.assertEqual(turn.calls.last().error_code, expected)
                BrainstormTurn.objects.all().delete()
                BrainstormSession.objects.all().delete()

    def test_strict_reviewer_rejects_duplicate_and_extra_keys(self):
        for text in ('{"decision":"approve","decision":"reject","reason_code":"approved"}',
                     '{"decision":"approve","reason_code":"approved","draft":"X"}',
                     '{"decision":"approve","reason_code":"other_policy_violation"}'):
            with self.assertRaises(Exception):
                parse_review(text)

    def test_editorial_size_is_bounded_before_reviewer_call(self):
        solution = self.problem.solution
        solution.content = 'x' * (self.version.max_code_chars + 1)
        solution.save(update_fields=['content'])
        turn, gateway = self.generate([result('draft')])
        self.assertEqual(gateway.call_count, 1)
        self.assertEqual(turn.status, 'failed')
        self.assertEqual(turn.error_code, 'context_limit')
        self.assertEqual(turn.used_provider_calls, 1)
        self.assertFalse(turn.published_messages.exists())

    def test_revoke_before_first_call_or_before_publish(self):
        turn, _, _ = self.claim()
        self.switch.enabled = False
        self.switch.save(update_fields=['enabled'])
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate') as gateway:
            run_brainstorm(turn.pk)
        gateway.assert_not_called()
        turn.refresh_from_db()
        self.assertEqual((turn.error_code, turn.used_provider_calls), ('brainstorm_disabled', 0))
        self.assertEqual(turn.current_code_snapshot, '')
        self.switch.enabled = True
        self.switch.save(update_fields=['enabled'])
        finish_turn(turn.pk, 'failed')
        next_turn, _, _ = self.claim('next')

        def disable(role, messages, max_tokens):
            if role == 'brainstorm_review':
                self.switch.enabled = False
                self.switch.save(update_fields=['enabled'])
                return verdict('approve', 'approved')
            return result('approved in memory only')

        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=disable):
            run_brainstorm(next_turn.pk)
        next_turn.refresh_from_db()
        self.assertEqual(next_turn.status, 'failed')
        self.assertEqual(next_turn.error_code, 'brainstorm_disabled')
        self.assertFalse(next_turn.published_messages.exists())

    def test_contest_switch_and_access_recheck_during_inference(self):
        participation = self.contest('pipeline-contest')
        for mode in ('contest_switch', 'ended', 'access'):
            with self.subTest(mode=mode):
                turn, _, _ = self.claim('contest-' + mode)

                def revoke(role, messages, max_tokens):
                    if role == 'brainstorm_review':
                        if mode == 'contest_switch':
                            BrainstormContestConfig.objects.filter(contest=participation.contest).update(enabled=False)
                        elif mode == 'ended':
                            participation.contest.end_time = timezone.now()-timedelta(seconds=1)
                            participation.contest.save(update_fields=['end_time'])
                        else:
                            participation.contest.is_visible = False
                            participation.contest.save(update_fields=['is_visible'])
                        return verdict('approve', 'approved')
                    return result('Draft')

                with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=revoke):
                    run_brainstorm(turn.pk)
                turn.refresh_from_db()
                self.assertEqual(turn.status, 'failed')
                self.assertFalse(turn.published_messages.exists())
                participation.real_start = timezone.now()
                participation.save(update_fields=['real_start'])
                participation.contest.is_visible = True
                participation.contest.end_time = timezone.now()+timedelta(hours=2)
                participation.contest.save(update_fields=['is_visible', 'end_time'])
                BrainstormContestConfig.objects.filter(contest=participation.contest).update(enabled=True)


class BrainstormApiTests(BrainstormFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.session_url = reverse('mentor_brainstorm_send', args=[self.problem.code])
        self.post_url = reverse('mentor_brainstorm_post_turn', args=[self.problem.code])
        self.client.force_login(self.user)

    def post(self, payload=None):
        return self.client.post(self.post_url, data=json.dumps(payload or self.payload()),
                                content_type='application/json')

    def test_get_no_creation_and_post_enqueue_once(self):
        response = self.client.get(self.session_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['history'], [])
        self.assertFalse(BrainstormSession.objects.exists())
        with patch('mentor.tasks.generate_brainstorm.delay') as enqueue, self.captureOnCommitCallbacks(execute=True):
            response = self.post()
        self.assertEqual(response.status_code, 202)
        turn_id = response.json()['turn_id']
        enqueue.assert_called_once_with(turn_id)
        self.assertEqual(BrainstormMessage.objects.count(), 0)
        with patch('mentor.tasks.generate_brainstorm.delay') as enqueue, self.captureOnCommitCallbacks(execute=True):
            same = self.post()
        self.assertEqual(same.json()['turn_id'], turn_id)
        enqueue.assert_not_called()
        conflict = self.post(self.payload(question='Another question'))
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['error_code'], 'idempotency_conflict')
        blocked = self.post(self.payload('another-key'))
        self.assertEqual(blocked.json()['error_code'], 'turn_in_progress')
        self.assertEqual(self.client.get(reverse('mentor_brainstorm_turn', args=[turn_id])).json()['status'], 'pending')

    def test_api_only_approved_result_owner_and_no_secrets(self):
        turn, _, _ = self.claim()
        Solution.objects.create(problem=self.problem, content='SECRET EDITORIAL', is_public=False,
                                publish_on=timezone.now()+timedelta(days=1))
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=[
                result('Approved answer'), verdict('approve', 'approved')]):
            run_brainstorm(turn.pk)
        response = self.client.get(reverse('mentor_brainstorm_turn', args=[turn.pk]))
        self.assertEqual(response.json()['answer'], 'Approved answer')
        session = self.client.get(self.session_url)
        self.assertEqual(len(session.json()['history']), 1)
        self.assertNotIn('print(1)', session.content.decode())
        self.assertNotIn('SECRET EDITORIAL', session.content.decode())
        outsider = User.objects.create_user('api-outsider')
        Profile.objects.create(user=outsider)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('mentor_brainstorm_turn', args=[turn.pk])).status_code, 404)
        self.assertEqual(self.client.get(self.session_url).json()['history'], [])

    def test_api_guards_legacy_no_entitlement_csrf_and_invalid_body(self):
        self.assertEqual(self.client.post(self.session_url, self.payload()).status_code, 410)
        self.assertFalse(BrainstormMessage.objects.exists())
        self.assertEqual(self.client.post(self.post_url, {'question': 'x'}).status_code, 400)
        self.assertEqual(self.post({'question': 'x', 'provider': 'fake'}).status_code, 400)
        self.switch.enabled = False
        self.switch.save(update_fields=['enabled'])
        self.assertEqual(self.post().json()['error_code'], 'brainstorm_disabled')
        self.switch.enabled = True
        self.switch.save(update_fields=['enabled'])
        from billing.models import Subscription
        Subscription.objects.filter(profile=self.profile).update(status='expired')
        self.assertEqual(self.post().json()['error_code'], 'subscription_required')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertNotEqual(csrf.post(self.post_url, json.dumps(self.payload()),
                                      content_type='application/json').status_code, 202)
        self.assertFalse(BrainstormTurn.objects.exists())

    def test_queue_failure_is_terminal_and_erases_code(self):
        with patch('mentor.tasks.generate_brainstorm.delay', side_effect=RuntimeError('broker detail')), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.post()
        turn = BrainstormTurn.objects.get(pk=response.json()['turn_id'])
        self.assertEqual(turn.status, 'failed')
        self.assertEqual(turn.error_code, 'queue_unavailable')
        self.assertEqual(turn.current_code_snapshot, '')
        self.assertEqual(turn.used_provider_calls, 0)
        self.assertFalse(BrainstormMessage.objects.exists())

    def test_expired_subscription_can_read_approved_history(self):
        turn, _, _ = self.claim()
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=[
                result('Safe answer'), verdict('approve', 'approved')]):
            run_brainstorm(turn.pk)
        from billing.models import Subscription
        Subscription.objects.filter(profile=self.profile).update(status='expired')
        self.assertEqual(self.client.get(self.session_url).json()['history'][0]['answer'], 'Safe answer')
        self.assertEqual(self.client.get(reverse('mentor_brainstorm_turn', args=[turn.pk])).json()['answer'],
                         'Safe answer')
        self.assertEqual(self.post(self.payload('new')).json()['error_code'], 'subscription_required')

    def test_contest_history_read_only_after_end_and_scope_isolation(self):
        contest = self.contest('api-contest')
        turn, _, _ = self.claim()
        with patch('mentor.brainstorm_pipeline.ai_gateway.generate', side_effect=[
                result('Contest answer'), verdict('approve', 'approved')]):
            run_brainstorm(turn.pk)
        contest.contest.end_time = timezone.now()-timedelta(seconds=2)
        contest.contest.save(update_fields=['end_time'])
        # ContestMiddleware clears an ended current_contest before dispatch;
        # the current session is practice, while the old turn remains owner-readable.
        self.assertEqual(self.client.get(self.session_url).json()['history'], [])
        self.assertEqual(self.client.get(reverse('mentor_brainstorm_turn', args=[turn.pk])).json()['answer'],
                         'Contest answer')
        self.profile.current_contest = None
        self.profile.save(update_fields=['current_contest'])
        self.assertEqual(self.client.get(self.session_url).json()['history'], [])
        self.assertEqual(self.client.get(reverse('mentor_brainstorm_turn', args=[turn.pk])).json()['answer'],
                         'Contest answer')

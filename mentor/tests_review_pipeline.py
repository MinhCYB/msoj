import json
import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from ai_gateway.errors import AuthenticationError, RateLimitError, TimeoutError, UpstreamError
from ai_gateway.types import GatewayResult, Usage
from billing.constants import FEATURE_AI_REVIEW
from billing.models import Plan, Subscription
from judge.models import Language, Problem, ProblemGroup, Profile, Submission, SubmissionSource

from .models import AIReview, AIReviewAttempt
from .review_service import request_review
from .tasks import generate_review


class ReviewPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pipeline-owner', password='test')
        self.profile = Profile.objects.create(user=self.user)
        self.other = User.objects.create_user('pipeline-other', password='test')
        self.other_profile = Profile.objects.create(user=self.other)
        self.problem = Problem.objects.create(
            code='pipeline_problem', name='Review pipeline', description='Count numbers.',
            group=ProblemGroup.objects.create(name='pipeline-group', full_name='Pipeline group'),
            time_limit=1, memory_limit=65536, points=100, is_public=True,
        )
        self.language = Language.objects.create(key='REV_PIPE', name='Python review', common_name='Python',
                                                ace='python', pygments='python', extension='py')
        self.submission = self.make_submission()
        self.plan = Plan.objects.create(name='Review plan', scope='personal', pricing_type='per_day',
                                        price_per_day=1, features=[FEATURE_AI_REVIEW])
        self.subscription = Subscription.objects.create(profile=self.profile, plan=self.plan,
                                                        start_date=timezone.now() - timedelta(days=1),
                                                        end_date=timezone.now() + timedelta(days=1),
                                                        price_paid=1, status='active')
        self.url = reverse('mentor_submission_review', args=[self.submission.pk])
        self.valid_text = json.dumps({'overall_feedback': 'Try a boundary case.', 'approaches': []})

    def make_submission(self):
        submission = Submission.objects.create(user=self.profile, problem=self.problem, language=self.language,
                                                status='D', result='WA', judge_generation=1)
        SubmissionSource.objects.create(submission=submission, source='print(1)')
        return submission

    def claim(self, submission=None):
        with patch('mentor.tasks.generate_review.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                review, attempt, created = request_review((submission or self.submission).pk, self.profile)
        return review, attempt, created, delay

    def run_task(self, review, attempt, text=None, side_effect=None):
        with patch('mentor.review_service.ai_gateway.generate') as generate:
            generate.return_value = GatewayResult(text=self.valid_text if text is None else text,
                                                  provider='fake', requested_model='opaque', returned_model='upstream',
                                                  finish_reason='stop', usage=Usage(10, 5, 15))
            generate.side_effect = side_effect
            generate_review(review.pk, attempt.pk, attempt.review_revision)
        review.refresh_from_db()
        attempt.refresh_from_db()
        return generate

    def test_claim_duplicates_and_failed_manual_retry(self):
        review, attempt, created, delay = self.claim()
        self.assertTrue(created)
        delay.assert_called_once_with(review.pk, attempt.pk, attempt.review_revision)
        self.assertEqual(self.claim()[1].pk, attempt.pk)
        self.assertFalse(self.claim()[2])
        self.assertEqual(AIReviewAttempt.objects.count(), 1)
        self.assertIsNone(attempt.provider_call_started_at)
        attempt.status = review.status = 'running'
        attempt.save(update_fields=['status'])
        review.save(update_fields=['status'])
        self.assertEqual(self.claim()[1].pk, attempt.pk)
        generate = self.run_task(review, attempt)
        generate.assert_not_called()  # A manually marked running job must not be claimed again.
        review.status = attempt.status = 'failed'
        review.save(update_fields=['status'])
        attempt.save(update_fields=['status'])
        _, retry, created, delay = self.claim()
        self.assertTrue(created)
        self.assertEqual(retry.generation, attempt.generation + 1)
        delay.assert_called_once()

    def test_success_persists_metadata_and_succeeded_duplicate(self):
        review, attempt, _, _ = self.claim()
        generate = self.run_task(review, attempt)
        self.assertEqual(generate.call_args.args[0], 'review_default')
        self.assertEqual(review.status, 'succeeded')
        self.assertEqual(attempt.provider, 'fake')
        self.assertEqual((attempt.requested_model, attempt.returned_model, attempt.total_tokens),
                         ('opaque', 'upstream', 15))
        self.assertIsNotNone(attempt.provider_call_started_at)
        self.assertEqual(review.overall_feedback, 'Try a boundary case.')
        self.assertEqual(self.claim()[1].pk, attempt.pk)
        self.assertEqual(AIReviewAttempt.objects.count(), 1)
        self.subscription.end_date = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=['end_date'])
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.json()['overall_feedback'], 'Try a boundary case.')
        self.assertNotIn('source', response.json())
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_revision_change_stales_old_attempt_and_get_hides_output(self):
        review, attempt, _, _ = self.claim()
        self.run_task(review, attempt)
        Submission.objects.filter(pk=self.submission.pk).update(judge_generation=2)
        self.submission.refresh_from_db()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.json()['status'], 'stale')
        self.assertNotIn('overall_feedback', response.json())
        _, next_attempt, created, _ = self.claim()
        self.assertTrue(created)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'stale')
        self.assertNotEqual(next_attempt.review_revision, attempt.review_revision)

    def test_failure_outputs_and_gateway_errors(self):
        for text in ('', 'not json', '{"overall_feedback":"x","approaches":[],"extra":1}'):
            review, attempt, _, _ = self.claim()
            self.run_task(review, attempt, text=text)
            self.assertEqual(review.error_code, 'invalid_review_output')
        for exception, code in [(AuthenticationError(), 'authentication_failed'), (TimeoutError(), 'timeout'),
                                (RateLimitError(), 'rate_limited'), (UpstreamError(), 'upstream_unavailable')]:
            review, attempt, _, _ = self.claim()
            self.run_task(review, attempt, side_effect=exception)
            self.assertEqual(review.error_code, code)

    def test_unexpected_tool_calls_are_rejected(self):
        review, attempt, _, _ = self.claim()
        with patch('mentor.review_service.ai_gateway.generate', return_value=GatewayResult(
                self.valid_text, 'fake', 'opaque', tool_calls=[{'id': 'tool'}])):
            generate_review(review.pk, attempt.pk, attempt.review_revision)
        review.refresh_from_db()
        self.assertEqual(review.error_code, 'invalid_review_output')

    def test_stale_before_and_during_gateway_call(self):
        review, attempt, _, _ = self.claim()
        Submission.objects.filter(pk=self.submission.pk).update(judge_generation=2)
        generate = self.run_task(review, attempt)
        generate.assert_not_called()
        self.assertEqual(attempt.status, 'stale')
        self.submission.refresh_from_db()
        review, attempt, _, _ = self.claim()

        def rejudge(*args, **kwargs):
            Submission.objects.filter(pk=self.submission.pk).update(judge_generation=3)
            return GatewayResult(self.valid_text, 'fake', 'opaque')

        generate = self.run_task(review, attempt, side_effect=rejudge)
        generate.assert_called_once()
        self.assertEqual(attempt.status, 'stale')
        self.assertEqual(review.overall_feedback, '')

    def test_unsupported_context_before_call(self):
        review, attempt, _, _ = self.claim()
        self.language.file_only = True
        self.language.save(update_fields=['file_only'])
        generate = self.run_task(review, attempt)
        generate.assert_not_called()
        self.assertEqual(attempt.status, 'stale')

    def test_active_jobs_and_daily_call_limit(self):
        self.claim()
        self.claim(self.make_submission())
        with patch('mentor.tasks.generate_review.delay'):
            third = self.make_submission()
            from .review_service import ReviewDenied
            with self.assertRaises(ReviewDenied) as caught:
                request_review(third.pk, self.profile)
        self.assertEqual(caught.exception.code, 'too_many_active_reviews')
        AIReviewAttempt.objects.update(status='failed', provider_call_started_at=timezone.now())
        AIReview.objects.update(status='failed')
        for _ in range(8):
            old = AIReviewAttempt.objects.first()
            old.pk = None
            old.generation = AIReviewAttempt.objects.count() + 1
            old.save()
        with self.assertRaises(ReviewDenied) as caught:
            request_review(third.pk, self.profile)
        self.assertEqual(caught.exception.code, 'daily_review_quota')

    def test_owner_entitlement_csrf_and_safe_api(self):
        from .review_service import ReviewDenied
        with self.assertRaises(ReviewDenied) as caught:
            request_review(self.submission.pk, self.other_profile)
        self.assertEqual(caught.exception.code, 'not_found')
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.user)
        with patch('mentor.tasks.generate_review.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['status'], 'pending')
        self.assertNotIn('source', response.json())
        self.assertEqual(self.client.post(self.url, data={'model': 'other'}).status_code, 400)
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertNotEqual(csrf_client.post(self.url).status_code, 202)

    def test_enqueued_only_on_commit_and_queue_failure_is_visible(self):
        with patch('mentor.tasks.generate_review.delay', side_effect=RuntimeError('broker down')) as delay:
            with self.captureOnCommitCallbacks(execute=True):
                review, attempt, created = request_review(self.submission.pk, self.profile)
                delay.assert_not_called()
        self.assertTrue(created)
        delay.assert_called_once()
        review.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(review.status, 'failed')
        self.assertEqual(attempt.error_code, 'queue_unavailable')
        self.assertIsNone(attempt.provider_call_started_at)

    def test_api_returns_pending_failed_stale_and_safe_fields(self):
        review, attempt, _, _ = self.claim()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).json()['status'], 'pending')
        self.run_task(review, attempt, side_effect=TimeoutError())
        failed = self.client.get(self.url).json()
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error_code'], 'timeout')
        self.assertNotIn('source', failed)
        Submission.objects.filter(pk=self.submission.pk).update(judge_generation=2)
        self.assertEqual(self.client.get(self.url).json()['status'], 'stale')
        self.assertNotIn('error_code', self.client.get(self.url).json())

    def test_api_denies_live_contest_and_unsupported_inputs(self):
        from judge.models import Contest
        contest = Contest.objects.create(key='pipeline_contest', name='Pipeline contest',
                                         start_time=timezone.now() - timedelta(hours=1),
                                         end_time=timezone.now() + timedelta(hours=1))
        self.client.force_login(self.user)
        self.submission.contest_object = contest
        self.submission.save(update_fields=['contest_object'])
        self.assertEqual(self.client.post(self.url).json()['error_code'], 'contest_active')
        contest.end_time = timezone.now() - timedelta(seconds=1)
        contest.save(update_fields=['end_time'])
        self.submission.contest_object = None
        self.submission.save(update_fields=['contest_object'])
        self.language.file_only = True
        self.language.save(update_fields=['file_only'])
        self.assertEqual(self.client.post(self.url).json()['error_code'], 'file_only_source')
        self.language.file_only = False
        self.language.save(update_fields=['file_only'])
        self.problem.description = ''
        self.problem.pdf_url = 'https://example.test/problem.pdf'
        self.problem.save(update_fields=['description', 'pdf_url'])
        self.assertEqual(self.client.post(self.url).json()['error_code'], 'text_statement_missing')

    def test_verdict_api_eligibility(self):
        from .review_service import ReviewDenied
        for status, verdict in [('CE', 'CE'), ('D', 'WA'), ('D', 'AC')]:
            self.submission.status, self.submission.result = status, verdict
            self.submission.save(update_fields=['status', 'result'])
            review, attempt, _, _ = self.claim()
            review.status = attempt.status = 'failed'
            review.save(update_fields=['status'])
            attempt.save(update_fields=['status'])
        for status, verdict in [('IE', 'IE'), ('AB', 'AB')]:
            self.submission.status, self.submission.result = status, verdict
            self.submission.save(update_fields=['status', 'result'])
            with self.assertRaises(ReviewDenied) as caught:
                request_review(self.submission.pk, self.profile)
            self.assertEqual(caught.exception.code, 'judge_result_unsupported')

    def test_submission_page_panel_is_owner_only_and_eligibility_aware(self):
        url = reverse('submission_status', args=[self.submission.pk]) + '?panel=review'
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data['ai_review_can_request'])
        self.assertEqual(response.context_data['panel'], 'review')
        self.client.force_login(self.other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.user)
        self.submission.status, self.submission.result = 'D', 'IE'
        self.submission.save(update_fields=['status', 'result'])
        response = self.client.get(url)
        self.assertEqual(response.context_data['panel'], 'result')
        self.assertFalse(response.context_data.get('ai_review_can_request', False))

    def test_submission_panel_pretest_unavailable_and_existing_review_after_expiry(self):
        url = reverse('submission_status', args=[self.submission.pk]) + '?panel=review'
        self.client.force_login(self.user)
        self.submission.is_pretested = True
        self.submission.save(update_fields=['is_pretested'])
        response = self.client.get(url)
        self.assertTrue(response.context_data['submission'].is_pretested)
        self.assertEqual(response.context_data['panel'], 'review')
        review, _, _, _ = self.claim()
        self.subscription.end_date = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=['end_date'])
        response = self.client.get(url)
        self.assertEqual(response.context_data['panel'], 'review')
        self.assertFalse(response.context_data['ai_review_can_request'])
        self.assertEqual(review.status, 'pending')

    def test_submission_panel_hides_unsupported_new_review(self):
        url = reverse('submission_status', args=[self.submission.pk]) + '?panel=review'
        self.client.force_login(self.user)
        self.language.file_only = True
        self.language.save(update_fields=['file_only'])
        self.assertEqual(self.client.get(url).context_data['panel'], 'result')
        self.language.file_only = False
        self.language.save(update_fields=['file_only'])
        self.problem.description = ''
        self.problem.save(update_fields=['description'])
        self.assertEqual(self.client.get(url).context_data['panel'], 'result')


class ConcurrentReviewClaimTests(TransactionTestCase):
    def test_concurrent_post_claims_one_attempt_and_enqueues_once(self):
        user = User.objects.create_user('concurrent-review-owner')
        profile = Profile.objects.create(user=user)
        problem = Problem.objects.create(
            code='concurrent_review_problem', name='Concurrent review', description='Count numbers.',
            group=ProblemGroup.objects.create(name='conc-review', full_name='Concurrent review group'),
            time_limit=1, memory_limit=65536, points=100, is_public=True,
        )
        language = Language.objects.create(key='CONC_REV', name='Concurrent Python', common_name='Python',
                                           ace='python', pygments='python', extension='py')
        submission = Submission.objects.create(user=profile, problem=problem, language=language,
                                                status='D', result='WA', judge_generation=1)
        SubmissionSource.objects.create(submission=submission, source='print(1)')
        plan = Plan.objects.create(name='Concurrent review plan', scope='personal', pricing_type='per_day',
                                   price_per_day=1, features=[FEATURE_AI_REVIEW])
        Subscription.objects.create(profile=profile, plan=plan, start_date=timezone.now() - timedelta(days=1),
                                    end_date=timezone.now() + timedelta(days=1), price_paid=1, status='active')
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def claim():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                results.append(request_review(submission.pk, profile)[2])
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        with patch('mentor.tasks.generate_review.delay') as enqueue:
            threads = [threading.Thread(target=claim) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertCountEqual(results, [True, False])
        self.assertEqual(AIReviewAttempt.objects.filter(review__submission=submission).count(), 1)
        enqueue.assert_called_once()

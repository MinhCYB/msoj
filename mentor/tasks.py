"""AI Review worker; no automatic Celery retry of potentially billed calls."""

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from ai_gateway.errors import GatewayError
from judge.models import Profile, Submission

from .models import AIReview, AIReviewApproach, AIReviewAttempt
from .review_context import SubmissionContextBuilder, UnsupportedReview
from .review_service import MAX_PROVIDER_CALLS_PER_24_HOURS, ReviewDenied, ReviewService, _reserved_calls


def _current(review, attempt, revision, submission):
    if (review.current_generation != attempt.generation or review.current_revision != revision
            or attempt.review_revision != revision):
        return False
    try:
        return SubmissionContextBuilder().build(submission).revision == revision
    except UnsupportedReview:
        return False


def _finish(review_id, attempt_id, revision, *, result=None, feedback=None, approaches=None, error=None):
    with transaction.atomic():
        # Match request_review's submission -> review -> attempt lock order.
        submission_id = AIReview.objects.values_list('submission_id', flat=True).get(pk=review_id)
        submission = Submission.objects.select_for_update().select_related(
            'problem', 'language', 'contest_object', 'source').get(pk=submission_id)
        review = AIReview.objects.select_for_update().get(pk=review_id)
        attempt = AIReviewAttempt.objects.select_for_update().get(pk=attempt_id, review_id=review_id)
        if attempt.status != AIReview.STATUS_RUNNING:
            return
        now = timezone.now()
        if not _current(review, attempt, revision, submission):
            attempt.status = AIReview.STATUS_STALE
            attempt.completed_at = now
            attempt.save(update_fields=['status', 'completed_at'])
            if review.current_generation == attempt.generation:
                review.status = AIReview.STATUS_STALE
                review.overall_feedback = ''
                review.completed_at = now
                review.save(update_fields=['status', 'overall_feedback', 'completed_at'])
            return
        attempt.completed_at = review.completed_at = now
        if error:
            attempt.status = review.status = AIReview.STATUS_FAILED
            attempt.error_code = review.error_code = error
            review.overall_feedback = ''
        else:
            attempt.status = review.status = AIReview.STATUS_SUCCEEDED
            attempt.overall_feedback = review.overall_feedback = feedback
            attempt.provider = result.provider or ''
            attempt.requested_model = result.requested_model or ''
            attempt.returned_model = result.returned_model or ''
            attempt.finish_reason = result.finish_reason or ''
            if result.usage:
                attempt.input_tokens = result.usage.input_tokens
                attempt.output_tokens = result.usage.output_tokens
                attempt.total_tokens = result.usage.total_tokens
            AIReviewApproach.objects.bulk_create([AIReviewApproach(attempt=attempt, order=index, **item)
                                                  for index, item in enumerate(approaches)])
        attempt.save()
        review.save()


@shared_task
def generate_review(review_id, attempt_id, expected_revision):
    with transaction.atomic():
        submission_id = AIReview.objects.values_list('submission_id', flat=True).get(pk=review_id)
        submission = Submission.objects.select_for_update().select_related(
            'problem', 'language', 'contest_object', 'source').get(pk=submission_id)
        review = AIReview.objects.select_for_update().get(pk=review_id)
        attempt = AIReviewAttempt.objects.select_for_update().get(pk=attempt_id, review_id=review_id)
        if attempt.status != AIReview.STATUS_PENDING:
            return
        if not _current(review, attempt, expected_revision, submission):
            attempt.status = AIReview.STATUS_STALE
            attempt.save(update_fields=['status'])
            if review.current_generation == attempt.generation:
                review.status = AIReview.STATUS_STALE
                review.overall_feedback = ''
                review.save(update_fields=['status', 'overall_feedback'])
            return
        now = timezone.now()
        attempt.status = review.status = AIReview.STATUS_RUNNING
        attempt.started_at = review.started_at = now
        attempt.save(update_fields=['status', 'started_at'])
        review.save(update_fields=['status', 'started_at'])

    # Recheck before reserving the call. Lock the same Profile row used by POST
    # so concurrent jobs from this learner cannot exceed the rolling 24h cap.
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(pk=submission.user_id)
        submission = Submission.objects.select_for_update().select_related(
            'problem', 'language', 'contest_object', 'source').get(pk=review.submission_id)
        review = AIReview.objects.select_for_update().get(pk=review_id)
        attempt = AIReviewAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.status != AIReview.STATUS_RUNNING or not _current(review, attempt, expected_revision, submission):
            if attempt.status == AIReview.STATUS_RUNNING:
                attempt.status = AIReview.STATUS_STALE
                attempt.save(update_fields=['status'])
                if review.current_generation == attempt.generation:
                    review.status = AIReview.STATUS_STALE
                    review.overall_feedback = ''
                    review.save(update_fields=['status', 'overall_feedback'])
            return
        # Reservation counts all other pending/running attempts; the current one
        # was already counted during POST. Avoid ever charging on unsupported data.
        try:
            snapshot = SubmissionContextBuilder().build(submission)
        except UnsupportedReview:
            attempt.status = review.status = AIReview.STATUS_FAILED
            attempt.error_code = review.error_code = 'unsupported_context'
            attempt.save(update_fields=['status', 'error_code'])
            review.save(update_fields=['status', 'error_code'])
            return
        if _reserved_calls(profile.pk, timezone.now()) > MAX_PROVIDER_CALLS_PER_24_HOURS:
            attempt.status = review.status = AIReview.STATUS_FAILED
            attempt.error_code = review.error_code = 'daily_review_quota'
            attempt.save(update_fields=['status', 'error_code'])
            review.save(update_fields=['status', 'error_code'])
            return
        attempt.provider_call_started_at = timezone.now()
        attempt.save(update_fields=['provider_call_started_at'])

    try:
        result, feedback, approaches = ReviewService().generate(snapshot)
    except GatewayError as exc:
        _finish(review_id, attempt_id, expected_revision, error=exc.code)
    except ReviewDenied as exc:
        _finish(review_id, attempt_id, expected_revision, error=exc.code)
    except Exception:
        # Never log untrusted prompt, source or upstream exception body.
        _finish(review_id, attempt_id, expected_revision, error='review_unavailable')
    else:
        _finish(review_id, attempt_id, expected_revision, result=result, feedback=feedback,
                approaches=approaches)

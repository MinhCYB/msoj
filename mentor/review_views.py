"""Owner-only AI Review JSON API. No provider configuration accepted from clients."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from billing.constants import FEATURE_AI_REVIEW
from billing.services import is_active_for

from .models import AIReview, AIReviewAttempt
from .review_context import SubmissionContextBuilder, UnsupportedReview
from .review_service import ReviewDenied, owned_submission, request_review


def _error(code, status):
    return JsonResponse({'error_code': code}, status=status)


def _payload(review, attempt, submission):
    status = review.status
    try:
        revision = SubmissionContextBuilder().build(submission).revision
    except UnsupportedReview:
        revision = None
    if not revision or review.current_revision != revision or attempt.review_revision != revision:
        status = AIReview.STATUS_STALE
    result = {'review_id': review.pk, 'status': status, 'generation': attempt.generation}
    if status == AIReview.STATUS_SUCCEEDED:
        result['overall_feedback'] = review.overall_feedback
        result['approaches'] = list(attempt.approaches.values('title', 'description', 'complexity', 'practicality', 'order'))
    elif status == AIReview.STATUS_FAILED:
        result['error_code'] = review.error_code or 'review_unavailable'
    return result


@login_required
@require_http_methods(['GET', 'POST'])
def submission_review(request, submission_id):
    try:
        submission = owned_submission(request.profile.pk, submission_id)
    except ReviewDenied:
        return _error('not_found', 404)

    if request.method == 'GET':
        review = AIReview.objects.filter(submission=submission).first()
        if review is None:
            return _error('not_found', 404)
        attempt = AIReviewAttempt.objects.filter(review=review, generation=review.current_generation).first()
        if attempt is None:
            return _error('not_found', 404)
        return JsonResponse(_payload(review, attempt, submission))

    if not submission.problem.is_accessible_by(request.user):
        return _error('problem_inaccessible', 403)
    if not is_active_for(request.profile, FEATURE_AI_REVIEW):
        return _error('no_active_subscription', 403)
    # An empty form may have a multipart body; only reject supplied fields.
    if request.POST or request.FILES or (request.content_type == 'application/json' and request.body.strip() not in (b'', b'{}')):
        return _error('unexpected_request_body', 400)
    try:
        review, attempt, created = request_review(submission_id, request.profile)
    except ReviewDenied as exc:
        status = 429 if exc.code in ('daily_review_quota', 'too_many_active_reviews') else 400
        if exc.code == 'no_active_subscription':
            status = 403
        return _error(exc.code, status)
    # The task may have completed before this response if Celery is eager.
    review.refresh_from_db()
    attempt.refresh_from_db()
    return JsonResponse(_payload(review, attempt, submission),
                        status=200 if review.status == AIReview.STATUS_SUCCEEDED else 202)

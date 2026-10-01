"""Review eligibility and bounded, untrusted submission data (no prompt assembly)."""

import hashlib
import json
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


REVISION_SCHEMA = 'review-v1'
MAX_SOURCE_CHARS = 65536
MAX_DESCRIPTION_CHARS = 40000
MAX_DIAGNOSTIC_CHARS = 8000
ALLOWED_RESULTS = frozenset({'AC', 'PAC', 'WA', 'TLE', 'MLE', 'OLE', 'IR', 'RTE', 'SC'})


class UnsupportedReview(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def review_is_current(review, submission):
    """Never expose a stale or legacy review as the current result."""
    if review.status != 'succeeded' or not review.current_revision:
        return False
    try:
        return review.current_revision == SubmissionContextBuilder().build(submission).revision
    except UnsupportedReview:
        return False


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def review_eligibility(submission, *, now=None):
    """Return a stable denial code or None. Does not load testcase or source rows."""
    if submission.status == 'CE' and submission.result == 'CE':
        pass
    elif submission.status == 'D' and submission.result in ALLOWED_RESULTS:
        pass
    else:
        return 'judge_result_unsupported'

    contest = submission.contest_object
    if contest is not None:
        # Contest.ended is cached per instance; use its end time and a fresh clock.
        if contest.end_time >= (now or timezone.now()):
            return 'contest_active'
        try:
            participation = submission.contest.participation
        except ObjectDoesNotExist:
            participation = None
        if participation is not None and participation.end_time >= (now or timezone.now()):
            return 'contest_active'
    if submission.language.file_only:
        return 'file_only_source'
    if not submission.problem.description.strip():
        return 'text_statement_missing'
    return None


@dataclass(frozen=True)
class ReviewSnapshot:
    revision: str
    source_digest: str
    result_digest: str
    problem: dict
    submission: dict
    language: dict
    source: str


class SubmissionContextBuilder:
    def build(self, submission, *, now=None):
        reason = review_eligibility(submission, now=now)
        if reason:
            raise UnsupportedReview(reason)

        problem = submission.problem
        language = submission.language
        try:
            source = submission.source.source
        except ObjectDoesNotExist as exc:
            raise UnsupportedReview('source_missing') from exc
        if not source.strip() or len(source) > MAX_SOURCE_CHARS:
            raise UnsupportedReview('source_missing' if not source.strip() else 'source_too_large')
        description = problem.description.strip()
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise UnsupportedReview('text_statement_too_large')
        error = submission.error or ''
        diagnostic = error[:MAX_DIAGNOSTIC_CHARS]
        problem_data = {'code': problem.code, 'name': problem.name, 'description': description,
                        'time_limit': problem.time_limit, 'memory_limit': problem.memory_limit}
        language_data = {'key': language.key, 'name': language.name}
        submission_data = {'status': submission.status, 'result': submission.result, 'time': submission.time,
                           'memory': submission.memory, 'error': diagnostic,
                           'is_pretested': submission.is_pretested, 'judge_generation': submission.judge_generation}
        source_digest = _digest(_canonical({'language_key': language.key, 'source': source}))
        result_digest = _digest(_canonical({**submission_data, 'error_digest': _digest(error.encode('utf-8'))}))
        revision = REVISION_SCHEMA + ':' + _digest(_canonical({
            'judge_generation': submission.judge_generation,
            'source_digest': source_digest,
            'result_digest': result_digest,
        }))
        return ReviewSnapshot(revision, source_digest, result_digest, problem_data,
                              submission_data, language_data, source)

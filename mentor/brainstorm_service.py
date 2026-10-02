"""Deterministic Brainstorm claims; no provider calls, queueing or public messages."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from billing.constants import FEATURE_AI_BRAINSTORM
from billing.services import is_active_for
from judge.models import ContestParticipation, ContestProblem, Language, Profile

from .brainstorm_context import BrainstormContextBuilder, UnsupportedBrainstormContext, statement_for
from .models import BrainstormCall, BrainstormContestConfig, BrainstormPolicy, BrainstormSession, BrainstormTurn


ACTIVE = (BrainstormTurn.STATUS_PENDING, BrainstormTurn.STATUS_RUNNING)
REQUEST_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


class BrainstormDenied(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BrainstormInput:
    question: str
    approach: str
    current_code: str
    client_request_id: str
    language_key: str

    @classmethod
    def parse(cls, payload):
        if not isinstance(payload, dict) or set(payload) != {
                'question', 'approach', 'current_code', 'client_request_id', 'language_key'}:
            raise BrainstormDenied('invalid_question')
        if any(not isinstance(value, str) for value in payload.values()):
            raise BrainstormDenied('invalid_question')
        return cls(**payload)


@dataclass(frozen=True)
class BrainstormScope:
    key: str
    participation: object = None


def resolve_scope(profile, problem, *, now=None):
    """Only the profile's server-side current participation can select a contest scope."""
    now = now or timezone.now()
    participation_id = Profile.objects.filter(pk=profile.pk).values_list('current_contest_id', flat=True).first()
    if not participation_id:
        return BrainstormScope('practice')
    participation = ContestParticipation.objects.select_related('contest').filter(
        pk=participation_id, user_id=profile.pk).first()
    if participation is None or participation.spectate or participation.is_disqualified:
        raise BrainstormDenied('problem_not_accessible')
    if participation.end_time is None or participation.end_time < now:
        raise BrainstormDenied('contest_scope_ended')
    if participation.start > now:
        raise BrainstormDenied('problem_not_accessible')
    if not participation.contest.is_accessible_by(profile.user) or (
            participation.live and participation.contest.start_time > now):
        raise BrainstormDenied('problem_not_accessible')
    if not ContestProblem.objects.filter(contest_id=participation.contest_id, problem_id=problem.pk).exists():
        raise BrainstormDenied('problem_not_accessible')
    return BrainstormScope(f'participation:{participation.pk}', participation)


def _validate_input(data, problem, policy):
    if not data.question.strip() or not REQUEST_ID.fullmatch(data.client_request_id):
        raise BrainstormDenied('invalid_question')
    if any(len(value) > limit for value, limit in (
            (data.question, policy.max_question_chars), (data.approach, policy.max_approach_chars),
            (data.current_code, policy.max_code_chars))):
        raise BrainstormDenied('payload_too_large')
    language = Language.objects.filter(key=data.language_key).first()
    if language is None or language.file_only or not problem.allowed_languages.filter(pk=language.pk).exists():
        raise BrainstormDenied('unsupported_language')
    if not statement_for(problem):
        raise BrainstormDenied('unsupported_problem')
    return language


def request_digest(session, data, policy):
    canonical = json.dumps({'scope': session.scope_key, 'session': session.pk, 'problem': session.problem_id,
                            'profile': session.profile_id, 'question': data.question, 'approach': data.approach,
                            'code': data.current_code, 'language': data.language_key, 'policy': policy.pk},
                           sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _capacity(profile_id, policy, now):
    turns = BrainstormTurn.objects.filter(session__profile_id=profile_id)
    start, end = _day_window(now)
    today = turns.filter(created_at__gte=start, created_at__lt=end)
    if today.count() >= policy.max_turns_per_day_per_profile:
        raise BrainstormDenied('turn_quota_exceeded')
    active = turns.filter(status__in=ACTIVE)
    if active.count() >= policy.max_active_turns_per_profile:
        raise BrainstormDenied('active_turn_limit')
    # Started calls count for the day, even for terminal turns. Active unused reservations
    # hold capacity only until terminal; terminal unused reservations are released.
    started = turns.filter(calls__started_at__gte=start, calls__started_at__lt=end).values('calls__pk').distinct().count()
    held = active.aggregate(
        total=Sum(F('reserved_provider_calls') - F('used_provider_calls')))['total'] or 0
    if started + held + policy.max_application_calls_per_turn > policy.max_provider_calls_per_day_per_profile:
        raise BrainstormDenied('provider_call_quota_exceeded')


def _day_window(now):
    zone = timezone.get_current_timezone()
    date = timezone.localdate(now)
    return (timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()), zone),
            timezone.make_aware(timezone.datetime.combine(date + timedelta(days=1),
                                                          timezone.datetime.min.time()), zone))


def _hint_level(seconds, policy):
    if seconds >= policy.level_3_after_seconds:
        return 3
    if seconds >= policy.level_2_after_seconds:
        return 2
    return 1


def clear_sensitive_snapshot(turn):
    """Call on terminal completion/failure; digest and original length remain for audit."""
    BrainstormTurn.objects.filter(pk=turn.pk).update(current_code_snapshot='')
    turn.current_code_snapshot = ''


def clear_expired_snapshots(*, now=None):
    """On-demand safety sweep; no scheduler is introduced in Phase 3B."""
    return BrainstormTurn.objects.filter(code_expires_at__lte=now or timezone.now()).exclude(
        current_code_snapshot='').update(current_code_snapshot='')


def start_reserved_call(turn_id, role, ordinal, *, now=None):
    """Reserve-to-start accounting primitive for Phase 3C; never contacts a provider."""
    with transaction.atomic():
        profile_id = BrainstormTurn.objects.values_list('session__profile_id', flat=True).get(pk=turn_id)
        Profile.objects.select_for_update().get(pk=profile_id)
        turn = BrainstormTurn.objects.select_for_update().get(pk=turn_id)
        if turn.status not in ACTIVE or turn.used_provider_calls >= turn.reserved_provider_calls:
            raise BrainstormDenied('provider_call_quota_exceeded')
        if role not in (BrainstormCall.ROLE_GENERATE, BrainstormCall.ROLE_REVIEW) or ordinal < 1:
            raise BrainstormDenied('provider_call_quota_exceeded')
        existing = BrainstormCall.objects.filter(turn=turn, role=role, ordinal=ordinal).first()
        if existing:
            return existing, False
        now = now or timezone.now()
        start, end = _day_window(now)
        started_today = BrainstormCall.objects.filter(turn__session__profile_id=profile_id,
                                                      started_at__gte=start, started_at__lt=end).count()
        if started_today >= turn.policy_version.max_provider_calls_per_day_per_profile:
            raise BrainstormDenied('provider_call_quota_exceeded')
        call, created = BrainstormCall.objects.get_or_create(turn=turn, role=role, ordinal=ordinal,
                                                             defaults={'status': BrainstormCall.STATUS_STARTED,
                                                                       'started_at': now})
        if created:
            turn.used_provider_calls += 1
            turn.save(update_fields=['used_provider_calls'])
        return call, created


def finish_turn(turn_id, status, *, now=None):
    """Release unused calls and erase code at terminal transition, without publishing history."""
    if status not in (BrainstormTurn.STATUS_SUCCEEDED, BrainstormTurn.STATUS_FAILED):
        raise ValueError('A terminal status is required')
    with transaction.atomic():
        profile_id = BrainstormTurn.objects.values_list('session__profile_id', flat=True).get(pk=turn_id)
        Profile.objects.select_for_update().get(pk=profile_id)
        turn = BrainstormTurn.objects.select_for_update().get(pk=turn_id)
        if turn.status in ACTIVE:
            turn.status = status
            turn.completed_at = now or timezone.now()
            turn.current_code_snapshot = ''
            turn.save(update_fields=['status', 'completed_at', 'current_code_snapshot'])
        return turn


def claim_turn(profile, problem, payload, *, now=None):
    """Return (turn, structured_context, created). Profile lock serializes all quotas."""
    data = BrainstormInput.parse(payload)
    with transaction.atomic():
        profile = Profile.objects.select_for_update().select_related('user').get(pk=profile.pk)
        now = now or timezone.now()
        scope = resolve_scope(profile, problem, now=now)
        # Reuse judge visibility; an active virtual contest may precede its official
        # window, so its checked ContestProblem/membership authorizes that case.
        if not problem.is_accessible_by(profile.user) and not scope.participation:
            raise BrainstormDenied('problem_not_accessible')
        global_policy = BrainstormPolicy.objects.select_related('published_version').filter(pk=1).first()
        if global_policy is None or not global_policy.enabled or not global_policy.published_version_id or not global_policy.published_version.is_published:
            raise BrainstormDenied('brainstorm_disabled')
        if scope.participation and not BrainstormContestConfig.objects.filter(
                contest_id=scope.participation.contest_id, enabled=True).exists():
            raise BrainstormDenied('contest_brainstorm_disabled')
        if not is_active_for(profile, FEATURE_AI_BRAINSTORM):
            raise BrainstormDenied('subscription_required')
        policy = global_policy.published_version
        session = BrainstormSession.objects.select_for_update().filter(
            profile=profile, problem=problem, scope_key=scope.key).first()
        existing = (BrainstormTurn.objects.select_related('policy_version', 'language').filter(
            session=session, client_request_id=data.client_request_id).first() if session else None)
        if existing:
            # Idempotency compares the originally claimed policy, even if global policy has since changed.
            if existing.request_digest != request_digest(session, data, existing.policy_version):
                raise BrainstormDenied('idempotency_conflict')
            # A terminal or expired snapshot cannot safely be reconstructed from client input.
            context = (BrainstormContextBuilder().build(existing) if existing.status in ACTIVE and
                       existing.code_expires_at > now else None)
            return existing, context, False
        language = _validate_input(data, problem, policy)
        if session is None:
            session = BrainstormSession.objects.create(profile=profile, problem=problem, scope_key=scope.key,
                                                       participation=scope.participation)
        digest = request_digest(session, data, policy)
        if session.turns.filter(status__in=ACTIVE).count() >= policy.max_active_turns_per_session:
            raise BrainstormDenied('turn_in_progress')
        _capacity(profile.pk, policy, now)
        prior = session.turns.exists()
        # Legacy STUB sessions may predate approved turns; their old timer is not
        # evidence of learning time in this policy version.
        seconds = session.total_active_seconds if prior else 0
        if prior:
            seconds += min(max((now - session.last_activity_at).total_seconds(), 0), policy.idle_timeout_seconds)
        level = _hint_level(seconds, policy)
        turn = BrainstormTurn.objects.create(
            session=session, client_request_id=data.client_request_id, request_digest=digest,
            policy_version=policy, hint_level=level, question_snapshot=data.question,
            approach_snapshot=data.approach, current_code_snapshot=data.current_code,
            code_digest=hashlib.sha256(data.current_code.encode('utf-8')).hexdigest(),
            code_length=len(data.current_code), code_expires_at=now + timedelta(hours=min(policy.code_retention_hours, 24)),
            language=language, reserved_provider_calls=policy.max_application_calls_per_turn)
        try:
            context = BrainstormContextBuilder().build(turn)
        except UnsupportedBrainstormContext as exc:
            raise BrainstormDenied(exc.args[0]) from exc
        turn.history_truncated = context.history_truncated
        turn.save(update_fields=['history_truncated'])
        session.total_active_seconds = int(seconds)
        session.last_activity_at = now
        session.save(update_fields=['total_active_seconds', 'last_activity_at'])
        return turn, context, True

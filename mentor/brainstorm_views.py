"""Owner-only Brainstorm JSON API. No user-selected scope, model or provider."""

import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from judge.models import ContestProblem, Problem, Profile

from .brainstorm_service import (BrainstormDenied, _hint_level, claim_turn, resolve_scope)
from .models import (BrainstormContestConfig, BrainstormMessage, BrainstormPolicy,
                     BrainstormSession, BrainstormTurn)


def _error(code, status):
    return JsonResponse({'error_code': code}, status=status)


def _scope(profile, problem):
    try:
        scope = resolve_scope(profile, problem)
    except BrainstormDenied as exc:
        return None, _error(exc.code, 403)
    if not scope.participation and not problem.is_accessible_by(profile.user):
        return None, _error('problem_not_accessible', 403)
    return scope, None


def _readable_ended_scope(profile, problem):
    """Only the server-owned ended participation is readable; POST remains denied."""
    participation = Profile.objects.select_related('current_contest__contest').get(pk=profile.pk).current_contest
    if (participation is None or participation.user_id != profile.pk or not participation.ended or
            participation.is_disqualified or participation.spectate or
            not participation.contest.is_accessible_by(profile.user) or
            not ContestProblem.objects.filter(contest=participation.contest, problem=problem).exists()):
        return None
    return f'participation:{participation.pk}'


def _readable_historical_turn(turn, profile):
    """A former participant may poll their own ended turn after middleware clears current_contest."""
    session = turn.session
    if not session.participation_id:
        return False
    participation = session.participation
    return (participation.user_id == profile.pk and participation.ended and not participation.is_disqualified and
            not participation.spectate and participation.contest.is_accessible_by(profile.user) and
            ContestProblem.objects.filter(contest=participation.contest, problem=session.problem).exists())


def _turn_state(turn):
    data = {'turn_id': turn.pk, 'status': turn.status, 'hint_level': turn.hint_level,
            'history_truncated': turn.history_truncated,
            'created_at': turn.created_at.isoformat(),
            'completed_at': turn.completed_at.isoformat() if turn.completed_at else None}
    if turn.status == BrainstormTurn.STATUS_FAILED:
        data['error_code'] = turn.error_code or 'brainstorm_unavailable'
    if turn.status == BrainstormTurn.STATUS_SUCCEEDED:
        approved = turn.published_messages.filter(role=BrainstormMessage.ROLE_AI, is_legacy_stub=False).first()
        if approved:
            data['answer'] = approved.content
            data['visuals'] = approved.approved_visuals
    return data


@login_required
@require_http_methods(['GET'])
def session_state(request, problem_code):
    problem = get_object_or_404(Problem, code=problem_code)
    scope, error = _scope(request.profile, problem)
    scope_key = scope.key if scope else _readable_ended_scope(request.profile, problem)
    if scope_key is None:
        return error
    session = BrainstormSession.objects.filter(profile=request.profile, problem=problem, scope_key=scope_key).first()
    history = []
    active = None
    if session:
        # Require exactly one student and one AI message from the same successful turn.
        rows = (BrainstormMessage.objects.filter(session=session, is_legacy_stub=False,
                                                 turn__status=BrainstormTurn.STATUS_SUCCEEDED)
                .order_by('turn__created_at', 'turn_id', 'created_at', 'pk'))
        pairs = {}
        for message in rows:
            pairs.setdefault(message.turn_id, []).append(message)
        history = [{'turn_id': turn_id, 'question': messages[0].content,
                    'approach': messages[0].described_approach, 'answer': messages[1].content,
                    'visuals': messages[1].approved_visuals, 'hint_level': messages[1].hint_level_granted}
                   for turn_id, messages in pairs.items()
                   if len(messages) == 2 and messages[0].role == 'student' and messages[1].role == 'ai']
        running = session.turns.filter(status__in=(BrainstormTurn.STATUS_PENDING,
                                                   BrainstormTurn.STATUS_RUNNING)).order_by('-pk').first()
        active = _turn_state(running) if running else None
    policy = BrainstormPolicy.objects.select_related('published_version').filter(pk=1).first()
    enabled = bool(policy and policy.enabled and policy.published_version and policy.published_version.is_published)
    if scope is None:
        enabled = False
    elif scope.participation:
        enabled = enabled and BrainstormContestConfig.objects.filter(
            contest_id=scope.participation.contest_id, enabled=True).exists()
    hint = _hint_level(session.total_active_seconds, policy.published_version) if session and enabled else 1
    return JsonResponse({'history': history, 'active_turn': active, 'available': enabled,
                         'hint_level': hint})


@login_required
@require_http_methods(['POST'])
def post_turn(request, problem_code):
    problem = get_object_or_404(Problem, code=problem_code)
    if request.content_type != 'application/json':
        return _error('invalid_question', 400)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _error('invalid_question', 400)
    try:
        with transaction.atomic():
            turn, _, created = claim_turn(request.profile, problem, payload)
            if created:
                from .tasks import generate_brainstorm

                def enqueue():
                    try:
                        generate_brainstorm.delay(turn.pk)
                    except Exception:
                        # A broker outage must not leave an unprocessed reservation and code snapshot.
                        from .brainstorm_service import finish_turn
                        with transaction.atomic():
                            Profile.objects.select_for_update().get(pk=request.profile.pk)
                            pending = BrainstormTurn.objects.select_for_update().get(pk=turn.pk)
                            if pending.status == BrainstormTurn.STATUS_PENDING:
                                pending.error_code = 'queue_unavailable'
                                pending.save(update_fields=['error_code'])
                                finish_turn(turn.pk, BrainstormTurn.STATUS_FAILED)

                transaction.on_commit(enqueue)
    except BrainstormDenied as exc:
        if exc.code == 'idempotency_conflict':
            status = 409
        elif exc.code in ('turn_in_progress', 'active_turn_limit', 'turn_quota_exceeded',
                          'provider_call_quota_exceeded'):
            status = 429
        elif exc.code in ('brainstorm_disabled', 'contest_brainstorm_disabled', 'contest_scope_ended',
                          'problem_not_accessible', 'subscription_required'):
            status = 403
        else:
            status = 400
        return _error(exc.code, status)
    turn.refresh_from_db()
    return JsonResponse(_turn_state(turn), status=202 if turn.status in (
        BrainstormTurn.STATUS_PENDING, BrainstormTurn.STATUS_RUNNING) else 200)


@login_required
@require_http_methods(['GET'])
def turn_state(request, turn_id):
    turn = get_object_or_404(BrainstormTurn.objects.select_related('session__problem',
                                                                  'session__participation__contest'),
                             pk=turn_id, session__profile=request.profile)
    scope, error = _scope(request.profile, turn.session.problem)
    scope_key = scope.key if scope else _readable_ended_scope(request.profile, turn.session.problem)
    if scope_key is None and not turn.session.participation_id:
        return error
    if scope_key != turn.session.scope_key:
        if not _readable_historical_turn(turn, request.profile):
            return _error('not_found', 404)
    return JsonResponse(_turn_state(turn))


@login_required
@require_http_methods(['GET', 'POST'])
def legacy_brainstorm(request, problem_code):
    """Compatibility: old POST can no longer write fake, unreviewed messages."""
    if request.method == 'POST':
        return _error('legacy_endpoint_retired', 410)
    return session_state(request, problem_code)

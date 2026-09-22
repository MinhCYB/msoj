from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from billing.constants import FEATURE_AI_BRAINSTORM
from billing.services import is_active_for
from judge.models import Problem

from .models import BrainstormMessage, BrainstormSession


@login_required
def brainstorm_send(request, problem_code):
    problem = get_object_or_404(Problem, code=problem_code)
    profile = request.profile

    if not is_active_for(profile, FEATURE_AI_BRAINSTORM):
        return JsonResponse({'allowed': False, 'reason': 'no_active_subscription'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'allowed': True}, status=200)

    described_approach = request.POST.get('described_approach', '').strip()
    content = request.POST.get('content', '').strip()
    if not described_approach or not content:
        return JsonResponse({'allowed': True, 'error': 'missing_fields'}, status=400)

    session, _ = BrainstormSession.objects.get_or_create(profile=profile, problem=problem)
    seconds_elapsed = (timezone.now() - session.last_activity_at).total_seconds()

    student_msg = BrainstormMessage(
        session=session,
        role=BrainstormMessage.ROLE_STUDENT,
        described_approach=described_approach,
        content=content,
    )
    student_msg.full_clean()
    student_msg.save()

    session.register_activity(seconds_elapsed)
    level = session.current_hint_level

    ai_msg = BrainstormMessage(
        session=session,
        role=BrainstormMessage.ROLE_AI,
        content=f'[STUB] Phản hồi giả lập cấp độ {level}.',
        hint_level_granted=level,
    )
    ai_msg.full_clean()
    ai_msg.save()

    return JsonResponse({'allowed': True, 'hint_level_granted': level})

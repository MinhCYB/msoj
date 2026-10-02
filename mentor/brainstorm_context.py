"""Structured, bounded Brainstorm data. All returned content is data, never instructions."""

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import get_language

from .models import BrainstormMessage, BrainstormTurn, ProblemHint


class UnsupportedBrainstormContext(Exception):
    pass


def statement_for(problem):
    language = get_language()
    translation = problem.translations.filter(language=language).first()
    return (translation.description if translation and translation.description.strip() else problem.description).strip()


@dataclass(frozen=True)
class BrainstormContext:
    # Reference and learner/history values are untrusted data; no system prompt is assembled here.
    problem: dict
    hints: tuple
    current: dict
    history: tuple
    history_truncated: bool


class BrainstormContextBuilder:
    def build(self, turn):
        session = turn.session
        problem = session.problem
        policy = turn.policy_version
        statement = statement_for(problem)
        if not statement:
            raise UnsupportedBrainstormContext('unsupported_problem')
        reference = {'code': problem.code, 'name': problem.name, 'statement': statement,
                     'time_limit': problem.time_limit, 'memory_limit': problem.memory_limit}
        # Hint ordering doubles as progression: first approved hint at level 1, first two at level 2, etc.
        hints = tuple(ProblemHint.objects.filter(problem=problem, enabled=True)
                      .values_list('content', flat=True)[:turn.hint_level])
        current = {'question': turn.question_snapshot, 'approach': turn.approach_snapshot,
                   'code': turn.current_code_snapshot, 'language': turn.language.key,
                   'hint_level': turn.hint_level}
        # Deterministic character budget; reserve all non-history data before considering history.
        budget = policy.max_question_chars + policy.max_approach_chars + policy.max_code_chars
        policy_reserved = sum(map(len, (policy.general_prompt, policy.level_1_prompt,
                                        policy.level_2_prompt, policy.level_3_prompt)))
        reserved = sum(len(str(value)) for value in reference.values()) + sum(map(len, hints)) + sum(
            len(str(value)) for value in current.values()) + policy_reserved
        if reserved > budget:
            raise UnsupportedBrainstormContext('payload_too_large')
        rows = BrainstormMessage.objects.filter(session=session, is_legacy_stub=False,
                                                turn__status=BrainstormTurn.STATUS_SUCCEEDED) \
            .order_by('turn__created_at', 'turn_id', 'created_at', 'pk').values(
                'turn_id', 'role', 'content', 'described_approach')
        grouped = {}
        for row in rows:
            pair = grouped.setdefault(row['turn_id'], {})
            if row['role'] not in pair:
                pair[row['role']] = row
            else:
                pair['duplicate'] = True
        pairs = [(pair['student']['content'], pair['student']['described_approach'], pair['ai']['content'])
                 for pair in grouped.values() if not pair.get('duplicate') and 'student' in pair and 'ai' in pair]
        history = []
        remaining = budget - reserved
        for pair in reversed(pairs):
            size = sum(map(len, pair))
            if size > remaining:
                break  # Only a contiguous recent suffix of complete approved pairs is allowed.
            remaining -= size
            history.append({'question': pair[0], 'approach': pair[1], 'answer': pair[2]})
        history.reverse()
        return BrainstormContext(reference, hints, current, tuple(history), len(history) < len(pairs))


def reviewer_reference(problem):
    """Internal-only reference for a future Reviewer; editorial remains untrusted data."""
    try:
        editorial = problem.solution.content
    except ObjectDoesNotExist:
        editorial = ''
    return {'editorial': editorial}

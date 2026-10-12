import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .constants import IDLE_TIMEOUT_SECONDS, compute_hint_level
from .roadmap_models import LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite, TopicLesson


# Policy templates are instructions; referenced application data is rendered in
# separate, lower-trust messages by a later phase.
PROMPT_TAGS = {
    'problem_statement', 'problem_hints', 'solution', 'editor_code',
    'student_approach', 'student_question', 'hint_level',
}
GENERATOR_PROMPT_TAGS = PROMPT_TAGS - {'solution'}
PROMPT_TAG_PATTERN = re.compile(r'{{\s*([^{}]+?)\s*}}')


def validate_brainstorm_template(value, *, reviewer=False):
    """Allow known placeholders only; never execute templates as code."""
    if not value or not value.strip():
        raise ValidationError('Prompt content is required before publishing.')
    tags = PROMPT_TAG_PATTERN.findall(value)
    allowed = PROMPT_TAGS if reviewer else GENERATOR_PROMPT_TAGS
    if (len(tags) != len(set(tags)) or set(tags) - allowed or
            '{{' in PROMPT_TAG_PATTERN.sub('', value) or '}}' in PROMPT_TAG_PATTERN.sub('', value)):
        raise ValidationError('Prompt contains unknown, duplicate, or malformed placeholders.')


class BrainstormPolicy(models.Model):
    """Singleton switch; a published version is immutable once in use."""
    singleton_id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    published_version = models.ForeignKey('BrainstormPolicyVersion', null=True, blank=True,
                                          on_delete=models.PROTECT, related_name='+')

    class Meta:
        permissions = (('manage_brainstorm_policy', 'Manage Brainstorm policy and global switch'),)

    def clean(self):
        if self.singleton_id != 1:
            raise ValidationError('Brainstorm uses a single global switch.')
        if self.enabled and (not self.published_version_id or not self.published_version.is_published):
            raise ValidationError('A published policy is required before enabling Brainstorm.')


class BrainstormPolicyVersion(models.Model):
    """Publish once; edit thresholds, quotas and prompts on a new draft version."""
    version = models.PositiveIntegerField(unique=True)
    is_published = models.BooleanField(default=False)
    level_2_after_seconds = models.PositiveIntegerField(default=600)
    level_3_after_seconds = models.PositiveIntegerField(default=1500)
    idle_timeout_seconds = models.PositiveIntegerField(default=300)
    max_active_turns_per_session = models.PositiveSmallIntegerField(default=1)
    max_active_turns_per_profile = models.PositiveSmallIntegerField(default=2)
    max_turns_per_day_per_profile = models.PositiveIntegerField(default=10)
    max_provider_calls_per_day_per_profile = models.PositiveIntegerField(default=60)
    max_application_calls_per_turn = models.PositiveSmallIntegerField(default=6)
    generator_max_tokens = models.PositiveIntegerField(default=1200)
    reviewer_max_tokens = models.PositiveIntegerField(default=256)
    max_question_chars = models.PositiveIntegerField(default=2000)
    max_approach_chars = models.PositiveIntegerField(default=4000)
    max_code_chars = models.PositiveIntegerField(default=20000)
    code_retention_hours = models.PositiveSmallIntegerField(default=24)
    general_prompt = models.TextField(blank=True)
    level_1_prompt = models.TextField(blank=True)
    level_2_prompt = models.TextField(blank=True)
    level_3_prompt = models.TextField(blank=True)
    reviewer_prompt = models.TextField(blank=True)
    updated_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-version']
        permissions = (('manage_brainstorm_prompts', 'Manage Brainstorm prompt versions'),)

    def clean(self):
        if not 0 < self.level_2_after_seconds < self.level_3_after_seconds:
            raise ValidationError('Hint thresholds must be ordered and positive.')
        positive = ('idle_timeout_seconds', 'max_active_turns_per_session', 'max_active_turns_per_profile',
                    'max_turns_per_day_per_profile', 'max_provider_calls_per_day_per_profile',
                    'max_application_calls_per_turn', 'max_question_chars', 'max_approach_chars',
                     'max_code_chars', 'code_retention_hours', 'generator_max_tokens', 'reviewer_max_tokens')
        if any(getattr(self, field) < 1 for field in positive):
            raise ValidationError('Quota, input limit, and retention values must be positive.')
        if self.max_active_turns_per_profile < self.max_active_turns_per_session:
            raise ValidationError('Profile concurrency must accommodate session concurrency.')
        if self.max_provider_calls_per_day_per_profile < self.max_application_calls_per_turn:
            raise ValidationError('Daily call budget must accommodate one full turn.')
        if self.is_published:
            for name in ('general_prompt', 'level_1_prompt', 'level_2_prompt', 'level_3_prompt'):
                validate_brainstorm_template(getattr(self, name))
            validate_brainstorm_template(self.reviewer_prompt, reviewer=True)
        elif self.published_at:
            raise ValidationError('Draft versions cannot have a publication timestamp.')

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, is_published=True).exists():
            raise ValidationError('Published Brainstorm policies are immutable; create a new version.')
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Brainstorm policy v{self.version}'


class BrainstormContestConfig(models.Model):
    contest = models.OneToOneField('judge.Contest', on_delete=models.CASCADE, related_name='mentor_brainstorm_config')
    enabled = models.BooleanField(default=False)


class ProblemHint(models.Model):
    problem = models.ForeignKey('judge.Problem', on_delete=models.CASCADE, related_name='mentor_brainstorm_hints')
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ['order', 'pk']

    def clean(self):
        if not self.content.strip():
            raise ValidationError({'content': 'A hint cannot be empty.'})




class BrainstormSession(models.Model):
    profile = models.ForeignKey('judge.Profile', on_delete=models.CASCADE, related_name='mentor_brainstorm_sessions')
    problem = models.ForeignKey('judge.Problem', on_delete=models.CASCADE, related_name='mentor_brainstorm_sessions')
    scope_key = models.CharField(max_length=64, default='practice')
    participation = models.ForeignKey('judge.ContestParticipation', null=True, blank=True, on_delete=models.PROTECT,
                                      related_name='mentor_brainstorm_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    total_active_seconds = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['profile', 'problem', 'scope_key'],
                                                name='mentor_brainstorm_scope_uniq'),
                       models.CheckConstraint(check=(Q(scope_key='practice', participation__isnull=True) |
                                                     (~Q(scope_key='practice') & Q(participation__isnull=False))),
                                              name='mentor_brainstorm_scope_kind_valid')]

    def clean(self):
        if self.participation_id is None:
            if self.scope_key != 'practice':
                raise ValidationError('Practice session must use the practice scope.')
        elif self.scope_key != f'participation:{self.participation_id}' or self.participation.user_id != self.profile_id:
            raise ValidationError('Contest session must match its owner and participation scope.')

    @property
    def current_hint_level(self):
        return compute_hint_level(self.total_active_seconds)

    def register_activity(self, seconds_elapsed):
        now = timezone.now()
        elapsed_since_last_activity = (now - self.last_activity_at).total_seconds()
        seconds_to_add = seconds_elapsed if elapsed_since_last_activity <= IDLE_TIMEOUT_SECONDS else 0

        self.total_active_seconds = F('total_active_seconds') + seconds_to_add
        self.last_activity_at = now
        self.save(update_fields=['total_active_seconds', 'last_activity_at'])
        self.refresh_from_db(fields=['total_active_seconds', 'last_activity_at'])

    def __str__(self):
        return f'{self.profile} - {self.problem}'


class BrainstormMessage(models.Model):
    ROLE_STUDENT = 'student'
    ROLE_AI = 'ai'
    ROLE_CHOICES = ((ROLE_STUDENT, 'Học viên'), (ROLE_AI, 'AI'))

    session = models.ForeignKey(BrainstormSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    described_approach = models.TextField(
        blank=True,
        help_text='Bắt buộc điền khi role=student — học viên phải mô tả hướng đang nghĩ trước khi nhận phản hồi AI',
    )
    content = models.TextField()
    hint_level_granted = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Chỉ có giá trị khi role=ai, ghi lại cấp độ tại thời điểm trả lời để audit',
    )
    turn = models.ForeignKey('BrainstormTurn', null=True, blank=True, on_delete=models.PROTECT,
                             related_name='published_messages')
    is_legacy_stub = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.role == self.ROLE_STUDENT and not self.described_approach.strip():
            raise ValidationError({'described_approach': 'Học viên phải mô tả hướng đang nghĩ.'})
        if self.role == self.ROLE_AI and self.hint_level_granted not in {1, 2, 3}:
            raise ValidationError({'hint_level_granted': 'Phản hồi AI phải có cấp độ gợi ý từ 1 đến 3.'})

    class Meta:
        ordering = ['created_at', 'pk']

    def save(self, *args, **kwargs):
        if self.turn_id is None and not self.is_legacy_stub:
            # The existing STUB still writes messages in Phase 3A; never label
            # those rows as reviewer-approved while that endpoint remains.
            self.is_legacy_stub = True
        if self.turn_id and (self.turn.session_id != self.session_id or self.is_legacy_stub):
            raise ValidationError('Published message must belong to its turn and cannot be legacy.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_role_display()} message for {self.session}'


class BrainstormTurn(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = tuple((value, value.title()) for value in (
        STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED))

    session = models.ForeignKey(BrainstormSession, on_delete=models.CASCADE, related_name='turns')
    client_request_id = models.CharField(max_length=64)
    request_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    policy_version = models.ForeignKey(BrainstormPolicyVersion, on_delete=models.PROTECT, related_name='turns')
    hint_level = models.PositiveSmallIntegerField()
    question_snapshot = models.TextField()
    approach_snapshot = models.TextField()
    current_code_snapshot = models.TextField(blank=True)
    code_digest = models.CharField(max_length=64)
    code_length = models.PositiveIntegerField(default=0)
    code_expires_at = models.DateTimeField()
    language = models.ForeignKey('judge.Language', on_delete=models.PROTECT)
    history_truncated = models.BooleanField(default=False)
    reserved_provider_calls = models.PositiveSmallIntegerField(default=0)
    used_provider_calls = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['session', 'client_request_id'],
                                                name='mentor_brainstorm_turn_request_uniq'),
                       models.CheckConstraint(check=Q(hint_level__gte=1, hint_level__lte=3),
                                              name='mentor_brainstorm_hint_level_valid')]


class BrainstormCall(models.Model):
    ROLE_GENERATE = 'generate'
    ROLE_REVIEW = 'review'
    ROLE_CHOICES = ((ROLE_GENERATE, 'Generate'), (ROLE_REVIEW, 'Review'))
    STATUS_RESERVED = 'reserved'
    STATUS_STARTED = 'started'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = tuple((value, value.title()) for value in (
        STATUS_RESERVED, STATUS_STARTED, STATUS_SUCCEEDED, STATUS_FAILED))

    turn = models.ForeignKey(BrainstormTurn, on_delete=models.CASCADE, related_name='calls')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    ordinal = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    provider = models.CharField(max_length=100, blank=True)
    requested_model = models.CharField(max_length=200, blank=True)
    returned_model = models.CharField(max_length=200, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    finish_reason = models.CharField(max_length=40, blank=True)
    reviewer_reason_code = models.CharField(max_length=40, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['turn', 'role', 'ordinal'],
                                                name='mentor_brainstorm_call_ordinal_uniq')]


class AIReview(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_STALE = 'stale'
    STATUS_CHOICES = tuple((status, status.title()) for status in (
        STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED, STATUS_STALE,
    ))

    submission = models.OneToOneField('judge.Submission', on_delete=models.CASCADE, related_name='mentor_ai_review')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    current_revision = models.CharField(max_length=80, blank=True)
    current_generation = models.PositiveIntegerField(default=0)
    overall_feedback = models.TextField(blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'AI review for submission #{self.submission_id}'


class AIReviewAttempt(models.Model):
    review = models.ForeignKey(AIReview, on_delete=models.CASCADE, related_name='attempts')
    generation = models.PositiveIntegerField()
    review_revision = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=AIReview.STATUS_CHOICES, default=AIReview.STATUS_PENDING)
    provider = models.CharField(max_length=100, blank=True)
    requested_model = models.CharField(max_length=200, blank=True)
    returned_model = models.CharField(max_length=200, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_tokens = models.PositiveIntegerField(null=True, blank=True)
    finish_reason = models.CharField(max_length=40, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    overall_feedback = models.TextField(blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    provider_call_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['review', 'generation'], name='mentor_review_attempt_generation_uniq')]
        indexes = [models.Index(fields=['status', 'requested_at'], name='mentor_attempt_status_idx')]

    def __str__(self):
        return f'AI review #{self.review_id}, attempt {self.generation}'


class AIReviewApproach(models.Model):
    COMPLEXITY_CHOICES = (
        ('O(1)', 'O(1)'), ('O(log n)', 'O(log n)'), ('O(n)', 'O(n)'),
        ('O(n log n)', 'O(n log n)'), ('O(n^2)', 'O(n²)'),
        ('O(n^3)', 'O(n³)'), ('O(2^n)', 'O(2^n)'), ('other', 'Khác'),
    )
    PRACTICALITY_CHOICES = (
        ('high', 'Cao'), ('medium', 'Trung bình'), ('low', 'Thấp'),
    )

    attempt = models.ForeignKey(AIReviewAttempt, on_delete=models.CASCADE, related_name='approaches')
    title = models.CharField(max_length=200)
    description = models.TextField()
    complexity = models.CharField(max_length=20, choices=COMPLEXITY_CHOICES)
    practicality = models.CharField(max_length=10, choices=PRACTICALITY_CHOICES)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.utils import timezone

from .constants import IDLE_TIMEOUT_SECONDS, compute_hint_level


class Topic(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RoadmapNode(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='roadmap_nodes')
    problem = models.ForeignKey(
        'judge.Problem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mentor_roadmap_nodes',
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    is_optional_review = models.BooleanField(
        default=False,
        help_text='Đánh dấu thủ công bởi admin: đây là node ôn tập phụ, không thuộc lộ trình chính bắt buộc',
    )
    organization = models.ForeignKey(
        'judge.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mentor_roadmap_nodes',
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.order}. {self.title}'


class RoadmapPrerequisite(models.Model):
    node = models.ForeignKey(RoadmapNode, on_delete=models.CASCADE, related_name='prerequisites')
    prerequisite = models.ForeignKey(RoadmapNode, on_delete=models.CASCADE, related_name='required_by')

    class Meta:
        unique_together = ('node', 'prerequisite')

    def __str__(self):
        return f'{self.node} requires {self.prerequisite}'


class BrainstormSession(models.Model):
    profile = models.ForeignKey('judge.Profile', on_delete=models.CASCADE, related_name='mentor_brainstorm_sessions')
    problem = models.ForeignKey('judge.Problem', on_delete=models.CASCADE, related_name='mentor_brainstorm_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    total_active_seconds = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('profile', 'problem')

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
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.role == self.ROLE_STUDENT and not self.described_approach.strip():
            raise ValidationError({'described_approach': 'Học viên phải mô tả hướng đang nghĩ.'})
        if self.role == self.ROLE_AI and self.hint_level_granted not in {1, 2, 3}:
            raise ValidationError({'hint_level_granted': 'Phản hồi AI phải có cấp độ gợi ý từ 1 đến 3.'})

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_role_display()} message for {self.session}'


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

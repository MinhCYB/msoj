from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .constants import ALL_FEATURES


class Plan(models.Model):
    SCOPE_PERSONAL = 'personal'
    SCOPE_ORGANIZATION = 'organization'
    SCOPE_CHOICES = (
        (SCOPE_PERSONAL, 'Cá nhân'),
        (SCOPE_ORGANIZATION, 'Tổ chức'),
    )

    PRICING_PER_DAY = 'per_day'
    PRICING_FIXED = 'fixed'
    PRICING_TYPE_CHOICES = (
        (PRICING_PER_DAY, 'Theo ngày'),
        (PRICING_FIXED, 'Giá cố định'),
    )

    name = models.CharField(max_length=100)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    pricing_type = models.CharField(max_length=10, choices=PRICING_TYPE_CHOICES)
    price_per_day = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fixed_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fixed_duration_days = models.PositiveIntegerField(null=True, blank=True)
    features = models.JSONField(
        default=list,
        blank=True,
        help_text='Danh sách feature mà gói này mở khoá, vd ["ai_brainstorm", "ai_review"]',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name='billing_plan_valid_pricing_fields',
                check=(
                    Q(
                        pricing_type='per_day',
                        price_per_day__isnull=False,
                        fixed_price__isnull=True,
                        fixed_duration_days__isnull=True,
                    )
                    | Q(
                        pricing_type='fixed',
                        fixed_price__isnull=False,
                        fixed_duration_days__isnull=False,
                        price_per_day__isnull=True,
                    )
                ),
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not isinstance(self.features, list):
            raise ValidationError({'features': 'Features phải là một danh sách.'})

        invalid_features = [feature for feature in self.features if feature not in ALL_FEATURES]
        if invalid_features:
            raise ValidationError(
                {'features': f'Feature không hợp lệ: {", ".join(map(str, invalid_features))}.'}
            )


class Subscription(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Đang hoạt động'),
        (STATUS_EXPIRED, 'Hết hạn'),
        (STATUS_CANCELLED, 'Đã huỷ'),
    )

    profile = models.ForeignKey(
        'judge.Profile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscriptions',
    )
    organization = models.ForeignKey(
        'judge.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    purchased_days = models.PositiveIntegerField(null=True, blank=True)
    price_paid = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name='billing_subscription_exactly_one_owner',
                check=(
                    Q(profile__isnull=False, organization__isnull=True)
                    | Q(profile__isnull=True, organization__isnull=False)
                ),
            ),
        ]
        indexes = [
            models.Index(fields=('status', 'end_date'), name='billing_sub_status_end_idx'),
        ]

    def __str__(self):
        owner = self.profile or self.organization
        return f'{self.plan.name} - {owner} - {self.end_date}'

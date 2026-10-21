from django.utils import timezone

from .constants import (
    ALL_FEATURES,
    FEATURE_AI_BRAINSTORM,
    FEATURE_AI_REVIEW,
    FEATURE_PERSONALIZED_ROADMAP,
)
from .models import Subscription


def is_active_for(profile, feature):
    """
    Kiểm tra profile có quyền dùng 1 feature cụ thể hay không.

    Điều kiện: có ít nhất một Subscription của profile này đang
    status='active', end_date >= now, VÀ feature nằm trong
    danh sách plan.features của subscription đó.
    """
    if feature not in ALL_FEATURES:
        raise ValueError(f'Unsupported billing feature: {feature}')

    active_subs = Subscription.objects.filter(
        Subscription.in_force_q(timezone.now()),
        profile=profile,
    ).select_related('plan')

    return any(feature in sub.plan.features for sub in active_subs)

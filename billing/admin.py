from django.contrib import admin
from django.utils import timezone

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'pricing_type', 'features_display', 'is_active')
    list_filter = ('scope', 'pricing_type', 'is_active')

    def features_display(self, obj):
        return ', '.join(obj.features) if obj.features else '—'

    features_display.short_description = 'Features'


class EffectiveStatusFilter(admin.SimpleListFilter):
    """Filter by the status that actually applies now, not the possibly stale stored value."""
    title = 'Trạng thái hiệu lực'
    parameter_name = 'effective_status'

    def lookups(self, request, model_admin):
        return Subscription.STATUS_CHOICES

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == Subscription.STATUS_ACTIVE:
            return queryset.filter(Subscription.in_force_q(now))
        if self.value() == Subscription.STATUS_EXPIRED:
            return queryset.filter(Subscription.lapsed_q(now))
        if self.value() == Subscription.STATUS_CANCELLED:
            return queryset.filter(status=Subscription.STATUS_CANCELLED)
        return queryset


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'organization', 'plan', 'effective_status_display', 'stored_status', 'end_date')
    list_filter = (EffectiveStatusFilter,)
    list_select_related = ('profile__user', 'organization', 'plan')

    @admin.display(description='Trạng thái hiệu lực')
    def effective_status_display(self, obj):
        return dict(Subscription.STATUS_CHOICES)[obj.effective_status()]

    @admin.display(description='Trạng thái lưu', ordering='status')
    def stored_status(self, obj):
        return obj.get_status_display()

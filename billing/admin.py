from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'pricing_type', 'features_display', 'is_active')
    list_filter = ('scope', 'pricing_type', 'is_active')

    def features_display(self, obj):
        return ', '.join(obj.features) if obj.features else '—'

    features_display.short_description = 'Features'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'organization', 'plan', 'status', 'end_date')
    list_filter = ('status',)

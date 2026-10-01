from django.contrib import admin, messages

from .client import list_models
from .errors import GatewayError
from .models import ModelRoute, ProviderConnection


@admin.register(ProviderConnection)
class ProviderConnectionAdmin(admin.ModelAdmin):
    list_display = ('slug', 'adapter', 'base_url', 'enabled', 'credential_available')
    search_fields = ('slug',)
    actions = ('check_catalog',)

    @admin.display(boolean=True, description='Credential available')
    def credential_available(self, obj):
        return obj.has_api_key

    @admin.action(description='Test connection via GET /models (no completion)')
    def check_catalog(self, request, queryset):
        for connection in queryset:
            try:
                count = len(list_models(connection))
            except GatewayError as exc:
                self.message_user(request, '%s: %s' % (connection.slug, exc.code), level=messages.ERROR)
            else:
                self.message_user(request, '%s: %d model IDs available' % (connection.slug, count))


@admin.register(ModelRoute)
class ModelRouteAdmin(admin.ModelAdmin):
    list_display = ('role', 'connection', 'model_id', 'enabled')
    list_filter = ('connection', 'enabled')
    search_fields = ('role', 'model_id')

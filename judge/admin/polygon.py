from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _, ngettext
from django.views.decorators.http import require_POST

from judge.models import PolygonProblem
from judge.tasks.polygon import polygon_refresh_index, polygon_sync_all, polygon_sync_busy, polygon_sync_problems

PERMISSION = 'judge.import_polygon_package'


class NeedsSyncFilter(admin.SimpleListFilter):
    title = _('revision')
    parameter_name = 'needs_sync'

    def lookups(self, request, model_admin):
        return (('1', _('Needs sync')),)

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(
                status__in=(PolygonProblem.NEW, PolygonProblem.OUTDATED, PolygonProblem.FAILED),
            )
        return queryset


class PolygonProblemAdmin(admin.ModelAdmin):
    change_list_template = 'admin/judge/polygonproblem/change_list.html'
    list_display = ('polygon_id', 'name', 'owner', 'code_link', 'status_badge', 'revisions', 'tag_list',
                    'last_synced')
    list_filter = ('status', NeedsSyncFilter, 'owner')
    search_fields = ('name', 'code', 'owner', 'message')
    list_per_page = 100
    actions = ['sync_selected', 'force_sync_selected']
    readonly_fields = [f.name for f in PolygonProblem._meta.fields]
    ordering = ('-polygon_id',)

    # ---- display -------------------------------------------------------------------------------------------

    @admin.display(description=_('MSOJ problem'), ordering='code')
    def code_link(self, obj):
        if obj.problem_id is None:
            return obj.code
        return format_html('<a href="{}">{}</a>', reverse('admin:judge_problem_change', args=[obj.problem_id]),
                           obj.code)

    @admin.display(description=_('status'), ordering='status')
    def status_badge(self, obj):
        label = obj.get_status_display()
        if obj.message:
            return format_html('<span title="{}">{}</span>', obj.message, label)
        return label

    @admin.display(description=_('synced / latest'))
    def revisions(self, obj):
        return f'{obj.synced_revision or "-"} / {obj.latest_revision or "-"}'

    @admin.display(description=_('tags'))
    def tag_list(self, obj):
        return ', '.join(obj.tags)

    # ---- permissions: the table is a mirror of Polygon, never edited by hand -----------------------------------

    def has_module_permission(self, request):
        return request.user.has_perm(PERMISSION)

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm(PERMISSION)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    # ---- sync entry points -------------------------------------------------------------------------------------

    def get_urls(self):
        return [
            path('refresh/', self.refresh_view, name='judge_polygonproblem_refresh'),
            path('sync-all/', self.sync_all_view, name='judge_polygonproblem_sync_all'),
            path('<int:pk>/sync/', self.sync_one_view, name='judge_polygonproblem_sync'),
        ] + super().get_urls()

    def _check(self, request):
        if not request.user.has_perm(PERMISSION):
            raise PermissionDenied()

    def _queued(self, request, what):
        if polygon_sync_busy():
            self.message_user(request, _('A Polygon sync is already running. Try again when it has finished.'),
                              messages.WARNING)
            return False
        self.message_user(request, _('%s queued. Reload this page to follow progress.') % what, messages.SUCCESS)
        return True

    @method_decorator(require_POST)
    def refresh_view(self, request):
        self._check(request)
        if self._queued(request, _('Refresh from Polygon')):
            polygon_refresh_index.delay()
        return HttpResponseRedirect(reverse('admin:judge_polygonproblem_changelist'))

    @method_decorator(require_POST)
    def sync_all_view(self, request):
        self._check(request)
        if self._queued(request, _('Sync of all problems')):
            polygon_sync_all.delay()
        return HttpResponseRedirect(reverse('admin:judge_polygonproblem_changelist'))

    @method_decorator(require_POST)
    def sync_one_view(self, request, pk):
        self._check(request)
        pp = PolygonProblem.objects.filter(pk=pk).first()
        if pp is None:
            raise Http404()
        if self._queued(request, _('Sync of %s') % pp.name):
            polygon_sync_problems.delay([pp.polygon_id], force=True)
        return HttpResponseRedirect(reverse('admin:judge_polygonproblem_changelist'))

    def _sync_selected(self, request, queryset, force):
        self._check(request)
        ids = list(queryset.values_list('polygon_id', flat=True))
        label = ngettext('Sync of %d problem', 'Sync of %d problems', len(ids)) % len(ids)
        if ids and self._queued(request, label):
            polygon_sync_problems.delay(ids, force=force)

    @admin.action(description=_('Sync selected problems (only if a newer revision exists)'))
    def sync_selected(self, request, queryset):
        self._sync_selected(request, queryset, force=False)

    @admin.action(description=_('Force re-import of selected problems'))
    def force_sync_selected(self, request, queryset):
        self._sync_selected(request, queryset, force=True)


class PolygonTagMappingAdmin(admin.ModelAdmin):
    list_display = ('tag', 'problem_type', 'problem_group')
    list_select_related = ('problem_type', 'problem_group')
    search_fields = ('tag',)
    fields = ('tag', 'problem_type', 'problem_group')

from django.contrib import admin
from django.core.exceptions import PermissionDenied

from .models import (
    AIReview,
    AIReviewAttempt,
    AIReviewApproach,
    BrainstormCall,
    BrainstormContestConfig,
    BrainstormMessage,
    BrainstormPolicy,
    BrainstormPolicyVersion,
    BrainstormSession,
    BrainstormTurn,
    ProblemHint,
)
from . import roadmap_admin  # noqa: F401


class ReadOnlyBrainstormAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields if field.name not in (self.exclude or ()))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BrainstormPolicy)
class BrainstormPolicyAdmin(admin.ModelAdmin):
    list_display = ('singleton_id', 'enabled', 'published_version')
    readonly_fields = ('singleton_id',)

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('mentor.manage_brainstorm_policy')

    def has_add_permission(self, request):
        return self.has_view_permission(request) and not BrainstormPolicy.objects.exists()

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'published_version':
            kwargs['queryset'] = BrainstormPolicyVersion.objects.filter(is_published=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BrainstormPolicyVersion)
class BrainstormPolicyVersionAdmin(admin.ModelAdmin):
    list_display = ('version', 'is_published', 'published_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_by', 'published_at')

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('mentor.manage_brainstorm_prompts')

    def has_add_permission(self, request):
        return self.has_view_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request) and (obj is None or not obj.is_published)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request) and obj is not None and not obj.is_published

    def save_model(self, request, obj, form, change):
        if change and BrainstormPolicyVersion.objects.filter(pk=obj.pk, is_published=True).exists():
            raise PermissionDenied
        obj.updated_by = request.user
        if obj.is_published and not obj.published_at:
            from django.utils import timezone
            obj.published_at = timezone.now()
        obj.save()


class ScopedMentorAdmin(admin.ModelAdmin):
    scope_field = None
    scope_permission = None

    def _can_edit(self, request, obj):
        return bool(obj and getattr(obj, self.scope_field).is_editable_by(request.user))

    def has_view_permission(self, request, obj=None):
        if not request.user.is_staff or not request.user.has_perm(self.scope_permission):
            return False
        return obj is None or self._can_edit(request, obj)

    def has_add_permission(self, request):
        return request.user.is_staff and request.user.has_perm(self.scope_permission)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not self._can_edit(request, obj):
            raise PermissionDenied
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if not self._can_edit(request, obj):
            raise PermissionDenied
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if any(not self._can_edit(request, obj) for obj in queryset):
            raise PermissionDenied
        super().delete_queryset(request, queryset)


@admin.register(ProblemHint)
class ProblemHintAdmin(ScopedMentorAdmin):
    scope_field = 'problem'
    scope_permission = 'judge.edit_own_problem'
    list_display = ('problem', 'order', 'enabled')

    def get_queryset(self, request):
        from judge.models import Problem
        return super().get_queryset(request).filter(problem__in=Problem.get_editable_problems(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'problem':
            from judge.models import Problem
            kwargs['queryset'] = Problem.get_editable_problems(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BrainstormContestConfig)
class BrainstormContestConfigAdmin(ScopedMentorAdmin):
    scope_field = 'contest'
    scope_permission = 'judge.edit_own_contest'
    list_display = ('contest', 'enabled')

    def has_view_permission(self, request, obj=None):
        if not request.user.is_staff or not (request.user.has_perm('judge.edit_own_contest') or
                                             request.user.has_perm('judge.edit_all_contest')):
            return False
        return obj is None or self._can_edit(request, obj)

    def has_add_permission(self, request):
        return self.has_view_permission(request)

    def get_queryset(self, request):
        from django.db.models import Q
        queryset = super().get_queryset(request)
        if request.user.has_perm('judge.edit_all_contest'):
            return queryset
        return queryset.filter(Q(contest__authors=request.profile) | Q(contest__curators=request.profile)).distinct()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'contest':
            from django.db.models import Q
            from judge.models import Contest
            queryset = Contest.objects.all()
            if not request.user.has_perm('judge.edit_all_contest'):
                queryset = queryset.filter(Q(authors=request.profile) | Q(curators=request.profile)).distinct()
            kwargs['queryset'] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AIReviewApproachInline(admin.TabularInline):
    model = AIReviewApproach
    extra = 0



@admin.register(BrainstormSession)
class BrainstormSessionAdmin(ReadOnlyBrainstormAdmin):
    list_display = ('profile', 'problem', 'scope_key', 'participation', 'total_active_seconds', 'started_at')
    exclude = ()


@admin.register(BrainstormMessage)
class BrainstormMessageAdmin(ReadOnlyBrainstormAdmin):
    list_display = ('session', 'turn', 'role', 'is_legacy_stub', 'hint_level_granted', 'created_at')
    list_filter = ('role', 'is_legacy_stub')


@admin.register(BrainstormTurn)
class BrainstormTurnAdmin(ReadOnlyBrainstormAdmin):
    list_display = ('session', 'status', 'policy_version', 'hint_level', 'reserved_provider_calls',
                    'used_provider_calls', 'created_at')
    exclude = ('current_code_snapshot', 'question_snapshot', 'approach_snapshot', 'request_digest', 'code_digest')


@admin.register(BrainstormCall)
class BrainstormCallAdmin(ReadOnlyBrainstormAdmin):
    list_display = ('turn', 'role', 'ordinal', 'status', 'provider', 'requested_model',
                    'returned_model', 'total_tokens', 'started_at')


@admin.register(AIReview)
class AIReviewAdmin(admin.ModelAdmin):
    list_display = ('submission', 'status', 'current_generation', 'created_at')


@admin.register(AIReviewAttempt)
class AIReviewAttemptAdmin(admin.ModelAdmin):
    list_display = ('review', 'generation', 'status', 'requested_at')
    inlines = (AIReviewApproachInline,)


@admin.register(AIReviewApproach)
class AIReviewApproachAdmin(admin.ModelAdmin):
    list_display = ('title', 'attempt', 'complexity', 'practicality', 'order')
    list_filter = ('complexity', 'practicality')

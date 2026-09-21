from django.contrib import admin

from .models import (
    AIReview,
    AIReviewApproach,
    BrainstormMessage,
    BrainstormSession,
    RoadmapNode,
    RoadmapPrerequisite,
    Topic,
)


class BrainstormMessageInline(admin.TabularInline):
    model = BrainstormMessage
    extra = 0


class AIReviewApproachInline(admin.TabularInline):
    model = AIReviewApproach
    extra = 0


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(RoadmapNode)
class RoadmapNodeAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'order', 'is_optional_review', 'organization')
    list_filter = ('topic', 'is_optional_review', 'organization')
    search_fields = ('title',)


@admin.register(RoadmapPrerequisite)
class RoadmapPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ('node', 'prerequisite')


@admin.register(BrainstormSession)
class BrainstormSessionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'problem', 'total_active_seconds', 'started_at', 'last_activity_at')
    inlines = (BrainstormMessageInline,)


@admin.register(BrainstormMessage)
class BrainstormMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'hint_level_granted', 'created_at')
    list_filter = ('role',)


@admin.register(AIReview)
class AIReviewAdmin(admin.ModelAdmin):
    list_display = ('submission', 'created_at')
    inlines = (AIReviewApproachInline,)


@admin.register(AIReviewApproach)
class AIReviewApproachAdmin(admin.ModelAdmin):
    list_display = ('title', 'review', 'complexity', 'practicality', 'order')
    list_filter = ('complexity', 'practicality')

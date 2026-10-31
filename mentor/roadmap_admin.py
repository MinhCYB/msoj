"""Django admin definitions for Roadmap and Learning content."""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from mptt.admin import MPTTModelAdmin
from mptt.forms import TreeNodeChoiceField

from judge.models import Problem
from judge.utils.views import NoBatchDeleteMixin
from judge.widgets import AdminHeavySelect2Widget, AdminMartorWidget
from mentor.models import (
    LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite, TopicLesson,
    TopicLessonQAAttempt, TopicLessonQAMessage, TopicLessonState,
)
from mentor.roadmap_models import Publication, lock_roadmap_forest
from mentor.roadmap_services import (
    allowed_problem, delete_node, delete_problem_link, require_write,
    save_content, save_node, save_problem_link,
)


class PublicationControlFormMixin:
    """Restricts publication transitions in forms and prevents forged POST."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user and not user.has_perm('mentor.publish_roadmap') and 'status' in self.fields:
            current = self.instance.status if (self.instance and self.instance.pk) else Publication.DRAFT
            self.fields['status'].choices = [(current, dict(Publication.choices).get(current, current))]

    def clean_status(self):
        if 'status' not in self.fields:
            return self.instance.status if (self.instance and self.instance.pk) else Publication.DRAFT
        status = self.cleaned_data.get('status')
        if not status:
            return self.instance.status if (self.instance and self.instance.pk) else Publication.DRAFT
        old = self.instance.status if (self.instance and self.instance.pk) else None
        if not (self.instance and self.instance.pk):
            if status == Publication.PUBLISHED and not (self.user and self.user.has_perm('mentor.publish_roadmap')):
                raise forms.ValidationError('You do not have permission to publish.')
        elif status != old and Publication.PUBLISHED in (status, old):
            if not (self.user and self.user.has_perm('mentor.publish_roadmap')):
                raise forms.ValidationError('You do not have permission to change publication status.')
        return status


class RoadmapForm(PublicationControlFormMixin, forms.ModelForm):
    class Meta:
        model = Roadmap
        fields = ('title', 'slug', 'status', 'visibility', 'organization', 'introduction')
        widgets = {'introduction': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('default_preview')})}


class LearningTopicForm(PublicationControlFormMixin, forms.ModelForm):
    confirm_shared = forms.BooleanField(required=False, label='Tôi hiểu thay đổi này áp dụng cho mọi nơi dùng chung nội dung')

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance.roadmap_nodes.count() > 1 and not data.get('confirm_shared'):
            self.add_error('confirm_shared', 'Xác nhận phạm vi ảnh hưởng trước khi lưu nội dung dùng chung.')
        return data

    class Meta:
        model = LearningTopic
        fields = ('name', 'slug', 'status', 'visibility', 'organization', 'introduction', 'confirm_shared')
        widgets = {'introduction': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('roadmap_markdown_preview')})}


class TopicLessonForm(PublicationControlFormMixin, forms.ModelForm):
    confirm_shared = forms.BooleanField(required=False, label='Tôi hiểu thay đổi này áp dụng cho mọi nơi dùng chung nội dung')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'slug' in self.fields:
            self.fields['slug'].required = False

    def clean(self):
        data = super().clean()
        topic = data.get('topic')
        if not self.instance.pk and not data.get('slug') and topic:
            from mentor.roadmap_workspace_forms import unique_slug
            data['slug'] = unique_slug(TopicLesson, data.get('title', ''), topic=topic)
        if topic and topic.roadmap_nodes.count() > 1 and not data.get('confirm_shared'):
            self.add_error('confirm_shared', 'Xác nhận phạm vi ảnh hưởng trước khi lưu bài giảng dùng chung.')
        return data

    class Meta:
        model = TopicLesson
        fields = ('topic', 'title', 'slug', 'position', 'status', 'summary', 'body', 'confirm_shared')
        widgets = {
            'summary': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('roadmap_markdown_preview')}),
            'body': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('roadmap_markdown_preview')}),
        }


class RoadmapNodeForm(PublicationControlFormMixin, forms.ModelForm):
    class Meta:
        model = RoadmapNode
        fields = ('roadmap', 'parent', 'type', 'title', 'slug', 'icon', 'position',
                  'difficulty', 'status', 'learning_topic', 'is_optional_review', 'summary', 'display_section')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'parent' in self.fields:
            if self.instance and self.instance.roadmap_id:
                qs = RoadmapNode.objects.filter(roadmap_id=self.instance.roadmap_id)
                if self.instance.pk:
                    descendants = self.instance.get_descendants(include_self=True).values_list('pk', flat=True)
                    qs = qs.exclude(pk__in=descendants)
                self.fields['parent'].queryset = qs
            elif self.initial.get('roadmap'):
                self.fields['parent'].queryset = RoadmapNode.objects.filter(roadmap_id=self.initial['roadmap'])


class NodeProblemForm(forms.ModelForm):
    class Meta:
        model = NodeProblem
        fields = ('problem', 'position')
        widgets = {'problem': AdminHeavySelect2Widget(data_view='problem_select2')}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_problem(self):
        problem = self.cleaned_data.get('problem')
        if problem and self.user:
            allowed_problem(self.user, problem.pk)
        return problem


class NodeProblemStandaloneForm(NodeProblemForm):
    class Meta(NodeProblemForm.Meta):
        fields = ('node', 'problem', 'position')


class RoadmapPrerequisiteForm(forms.ModelForm):
    class Meta:
        model = RoadmapPrerequisite
        fields = ('node', 'prerequisite', 'reason')
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        node, prereq = cleaned_data.get('node'), cleaned_data.get('prerequisite')
        if node and prereq:
            if node.pk == prereq.pk:
                self.add_error('prerequisite', 'A node cannot require itself.')
            elif node.roadmap_id != prereq.roadmap_id:
                self.add_error('prerequisite', 'Prerequisites must belong to the same roadmap.')
        return cleaned_data


class RoadmapStaffAdmin(NoBatchDeleteMixin, admin.ModelAdmin):
    actions = None

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and (
            super().has_view_permission(request, obj) or self.has_change_permission(request, obj)
        ))

    def has_add_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm(f'mentor.add_{self.opts.model_name}'))

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm(f'mentor.change_{self.opts.model_name}'))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm(f'mentor.delete_{self.opts.model_name}'))

    def delete_queryset(self, request, queryset):
        raise PermissionDenied('Bulk deletion is disabled.')

    def get_form(self, request, obj=None, change=False, **kwargs):
        FormClass = super().get_form(request, obj, change=change, **kwargs)

        class BoundStaffForm(FormClass):
            def __init__(sub_self, *args, **sub_kwargs):
                sub_kwargs.setdefault('user', request.user)
                super().__init__(*args, **sub_kwargs)

        return BoundStaffForm

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST':
            with transaction.atomic():
                lock_roadmap_forest()
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def delete_model(self, request, obj):
        lock_roadmap_forest()
        require_write(request.user, obj, 'delete')
        obj.delete()




class NodeProblemInline(admin.TabularInline):
    model = NodeProblem
    form = NodeProblemForm
    extra = 1
    fields = ('problem', 'position')

    def get_formset(self, request, obj=None, **kwargs):
        FormSet = super().get_formset(request, obj, **kwargs)

        class NodeProblemFormSetWithUser(FormSet):
            def _construct_form(sub_self, i, **form_kwargs):
                form_kwargs['user'] = request.user
                return super()._construct_form(i, **form_kwargs)

        return NodeProblemFormSetWithUser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'problem':
            kwargs['queryset'] = Problem.get_visible_problems(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.add_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.change_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.delete_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))


@admin.register(Roadmap)
class RoadmapAdmin(RoadmapStaffAdmin):
    form = RoadmapForm
    list_display = ('title', 'manage', 'status', 'visibility', 'organization', 'get_node_count')
    list_filter = ('status', 'visibility', 'organization')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('tree_revision',)
    change_form_template = 'admin/mentor/roadmap/change_form.html'
    fieldsets = ((None, {'fields': ('title', 'introduction', 'status', 'visibility', 'organization')}),
                 ('Nâng cao', {'classes': ('collapse',), 'fields': ('slug', 'tree_revision')}))

    def get_urls(self):
        from mentor.roadmap_workspace import roadmap_workspace
        from mentor.roadmap_staff_preview import roadmap_staff_preview

        def workspace(request, roadmap_id, node_id=None):
            return roadmap_workspace(request, roadmap_id, self.admin_site, node_id=node_id)

        def add_node(request, roadmap_id):
            return roadmap_workspace(request, roadmap_id, self.admin_site, adding=True)

        def preview(request, roadmap_id):
            return roadmap_staff_preview(request, roadmap_id, self.admin_site)

        return [
            path('<int:roadmap_id>/workspace/', self.admin_site.admin_view(workspace), name='mentor_roadmap_workspace'),
            path('<int:roadmap_id>/workspace/add/', self.admin_site.admin_view(add_node), name='mentor_roadmap_node_add'),
            path('<int:roadmap_id>/workspace/<int:node_id>/', self.admin_site.admin_view(workspace), name='mentor_roadmap_node_workspace'),
            path('<int:roadmap_id>/preview/', self.admin_site.admin_view(preview), name='mentor_roadmap_preview'),
        ] + super().get_urls()

    def manage(self, obj):
        return format_html('<a href="{}">Quản lý lộ trình</a>', reverse('admin:mentor_roadmap_workspace', args=[obj.pk]))
    manage.short_description = 'Nội dung và cấu trúc'

    def get_node_count(self, obj):
        return obj.nodes.count()
    get_node_count.short_description = 'Nhóm / chuyên đề'

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)


@admin.register(LearningTopic)
class LearningTopicAdmin(RoadmapStaffAdmin):
    form = LearningTopicForm
    change_form_template = 'admin/mentor/roadmap/content_change_form.html'
    list_display = ('name', 'slug', 'status', 'visibility', 'organization', 'get_node_count', 'get_lesson_count', 'content_revision')
    list_filter = ('status', 'visibility', 'organization')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('content_revision', 'usage_warning')
    inlines = []
    fieldsets = ((None, {'fields': ('name', 'introduction', 'status', 'visibility', 'organization', 'usage_warning', 'confirm_shared')}),
                 ('Nâng cao', {'classes': ('collapse',), 'fields': ('slug', 'content_revision')}))

    def get_node_count(self, obj):
        count = obj.roadmap_nodes.count()
        return f'{count} vị trí (DÙNG CHUNG)' if count > 1 else f'{count} vị trí'
    get_node_count.short_description = 'Nơi sử dụng'

    def get_lesson_count(self, obj):
        return obj.lessons.count()
    get_lesson_count.short_description = 'Bài giảng'

    def usage_warning(self, obj):
        if not obj or not obj.pk:
            return 'Bộ nội dung mới, chưa được gắn vào lộ trình.'
        nodes = list(obj.roadmap_nodes.select_related('roadmap').all())
        if not nodes:
            return 'Bộ nội dung chưa được gắn vào lộ trình.'
        items = [format_html('<li><a href="{}">{} → {}</a> [{}]</li>',
            reverse('admin:mentor_roadmap_node_workspace', args=[n.roadmap_id, n.pk]),
            n.roadmap.title, n.title, n.get_status_display()) for n in nodes]
        lessons = reverse('admin:mentor_topiclesson_changelist') + f'?topic__id__exact={obj.pk}'
        return format_html('Dùng tại {} vị trí:<ul>{}</ul><a href="{}">Quản lý từng bài giảng</a>',
            len(nodes), mark_safe(''.join(items)), lessons)
    usage_warning.short_description = 'Nơi sử dụng và phạm vi ảnh hưởng'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        topic = self.get_object(request, object_id)
        if topic and topic.roadmap_nodes.count() > 1:
            messages.warning(request, f'Bộ nội dung “{topic.name}” dùng chung tại {topic.roadmap_nodes.count()} vị trí; sửa ở đây sẽ áp dụng cho tất cả.')
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)



@admin.register(TopicLesson)
class TopicLessonAdmin(RoadmapStaffAdmin):
    form = TopicLessonForm
    list_display = ('title', 'topic', 'slug', 'position', 'status', 'content_revision')
    list_filter = ('status', 'topic')
    search_fields = ('title', 'slug', 'topic__name')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('content_revision',)
    change_form_template = 'admin/mentor/roadmap/lesson_change_form.html'
    fieldsets = ((None, {'fields': ('topic', 'title', 'status', 'summary', 'body', 'confirm_shared')}),
                 ('Nâng cao', {'classes': ('collapse',), 'fields': ('slug', 'position', 'content_revision')}))

    def workspace_node(self, request, lesson=None):
        from mentor.roadmap_workspace import can_read
        value = request.GET.get('workspace_node', '')
        if not (value.isascii() and value.isdigit() and can_read(request.user, Roadmap)
                and can_read(request.user, RoadmapNode)):
            return None
        node = RoadmapNode.objects.select_related('roadmap').filter(pk=value).first()
        if node and (lesson is None or node.learning_topic_id == lesson.topic_id):
            return node
        return None

    def get_changeform_initial_data(self, request):
        data = super().get_changeform_initial_data(request)
        node = self.workspace_node(request)
        if node and node.learning_topic_id:
            data['topic'] = node.learning_topic_id
            data['position'] = (TopicLesson.objects.filter(topic_id=node.learning_topic_id)
                .order_by('-position').values_list('position', flat=True).first() or 0) + 1
        return data

    def get_form(self, request, obj=None, change=False, **kwargs):
        FormClass = super().get_form(request, obj, change=change, **kwargs)
        node = self.workspace_node(request, obj)
        if node and node.learning_topic_id:
            topic_id = node.learning_topic_id

            class ContextLessonForm(FormClass):
                def __init__(sub_self, *args, **form_kwargs):
                    super().__init__(*args, **form_kwargs)
                    if 'topic' in sub_self.fields:
                        sub_self.fields['topic'].queryset = LearningTopic.objects.filter(pk=topic_id)

            return ContextLessonForm
        return FormClass

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        context = dict(extra_context or {})
        import json
        from pathlib import Path
        from .lesson_visuals import visual_blocks
        from .visual_algorithms import algorithm_document

        templates = {}
        for key in ('chart-table', 'prefix-sum', 'scene-geometry'):
            body = (Path(__file__).with_name('interactive_samples') / (key + '.md')).read_text(encoding='utf-8')
            templates[key] = json.loads(next(visual_blocks(body))[2])
        for key, inputs in (
            ('for-loop', {'start': 1, 'end': 4, 'step': 1}),
            ('bfs', {'n': 4, 'edges': [[0, 1], [0, 2], [1, 3]], 'source': 0}),
            ('dfs', {'n': 3, 'edges': [[0, 1], [1, 2]], 'source': 0}),
            ('matrix-chain', {'dimensions': [10, 20, 5, 30]}),
            ('dp-bitmask-matching', {'matrix': [[1, 1], [1, 1]]}),
        ):
            templates[key] = algorithm_document(key, inputs)
        context['visual_templates'] = templates
        lesson = self.get_object(request, object_id) if object_id else None
        node = self.workspace_node(request, lesson)
        if node:
            context['workspace_node'] = node
        return super().changeform_view(request, object_id, form_url, context)

    def response_add(self, request, obj, post_url_continue=None):
        if '_continue' not in request.POST and '_addanother' not in request.POST:
            node = self.workspace_node(request, obj)
            if node:
                return HttpResponseRedirect(reverse('admin:mentor_roadmap_node_workspace', args=[node.roadmap_id, node.pk]) + '?tab=lessons')
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if '_continue' not in request.POST and '_addanother' not in request.POST:
            node = self.workspace_node(request, obj)
            if node:
                return HttpResponseRedirect(reverse('admin:mentor_roadmap_node_workspace', args=[node.roadmap_id, node.pk]) + '?tab=lessons')
        return super().response_change(request, obj)

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)


class RoadmapOperationsAdmin(RoadmapStaffAdmin):
    """Learning history is operational evidence, never an authoring form."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)



@admin.register(TopicLessonState)
class TopicLessonStateAdmin(RoadmapOperationsAdmin):
    list_display = ('user', 'lesson', 'content_revision', 'offset', 'last_accessed_at')
    list_filter = ('content_revision',)
    search_fields = ('user__username', 'lesson__title')
    readonly_fields = ('last_accessed_at',)


@admin.register(TopicLessonQAMessage)
class TopicLessonQAMessageAdmin(RoadmapOperationsAdmin):
    list_display = ('user', 'lesson', 'content_revision', 'role', 'section', 'created_at')
    list_filter = ('role', 'content_revision')
    search_fields = ('user__username', 'lesson__title', 'content')
    readonly_fields = ('created_at',)


@admin.register(TopicLessonQAAttempt)
class TopicLessonQAAttemptAdmin(RoadmapOperationsAdmin):
    list_display = ('user', 'lesson', 'content_revision', 'status', 'claim_token', 'created_at', 'completed_at')
    list_filter = ('status', 'content_revision')
    search_fields = ('user__username', 'lesson__title', 'claim_token')
    readonly_fields = ('created_at', 'completed_at')

@admin.register(RoadmapNode)
class RoadmapNodeAdmin(RoadmapStaffAdmin, MPTTModelAdmin):
    form = RoadmapNodeForm
    mptt_indent_field = 'title'
    list_display = ('title', 'roadmap', 'parent', 'type', 'position', 'difficulty', 'status', 'learning_topic', 'get_problem_count', 'is_optional_review')
    list_filter = ('roadmap', 'type', 'status', 'difficulty', 'is_optional_review')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    actions = None
    inlines = [NodeProblemInline]

    def get_problem_count(self, obj):
        return obj.problem_links.count()
    get_problem_count.short_description = 'Problems'

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.append('roadmap')
        return tuple(readonly)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'parent':
            kwargs['form_class'] = TreeNodeChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        save_node(request.user, obj)

    def delete_model(self, request, obj):
        delete_node(request.user, obj.pk)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        node_problems_to_save = [inst for inst in instances if isinstance(inst, NodeProblem)]
        other_instances_to_save = [inst for inst in instances if not isinstance(inst, NodeProblem)]
        node_problems_to_delete = [obj for obj in formset.deleted_objects if isinstance(obj, NodeProblem)]
        other_deleted_to_delete = [obj for obj in formset.deleted_objects if not isinstance(obj, NodeProblem)]

        for obj in other_deleted_to_delete:
            obj.delete()

        # Handle same-problem replacements by updating the existing link instead of deleting it first.
        # This preserves the node's exercise invariant continuously without intermediate empty state.
        deleted_by_problem = {obj.problem_id: obj for obj in node_problems_to_delete}
        remaining_to_save = []
        for instance in node_problems_to_save:
            if instance.problem_id in deleted_by_problem:
                reused = deleted_by_problem.pop(instance.problem_id)
                reused.position = instance.position
                save_problem_link(request.user, reused)
            else:
                remaining_to_save.append(instance)

        remaining_to_delete = list(deleted_by_problem.values())

        # Save remaining new links first
        for instance in remaining_to_save:
            if not instance.node_id and form.instance.pk:
                instance.node = form.instance
            save_problem_link(request.user, instance)

        # Delete remaining deleted links (which do not clash with any saved links)
        for obj in remaining_to_delete:
            delete_problem_link(request.user, obj)

        for instance in other_instances_to_save:
            instance.save()

        formset.save_m2m()


@admin.register(NodeProblem)
class NodeProblemAdmin(RoadmapStaffAdmin):
    form = NodeProblemStandaloneForm
    list_display = ('node', 'problem', 'position')
    list_filter = ('node__roadmap',)
    search_fields = ('node__title', 'problem__code', 'problem__name')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'problem':
            kwargs['queryset'] = Problem.get_visible_problems(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.add_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.change_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.delete_nodeproblem') and request.user.has_perm('mentor.change_roadmapnode'))

    def save_model(self, request, obj, form, change):
        save_problem_link(request.user, obj)

    def delete_model(self, request, obj):
        delete_problem_link(request.user, obj)


    def delete_view(self, request, object_id, extra_context=None):
        try:
            return super().delete_view(request, object_id, extra_context)
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            self.message_user(request, f'Cannot delete exercise: {msg}', level=messages.ERROR)
            return HttpResponseRedirect(reverse('admin:mentor_nodeproblem_changelist'))

@admin.register(RoadmapPrerequisite)
class RoadmapPrerequisiteAdmin(RoadmapStaffAdmin):
    form = RoadmapPrerequisiteForm
    list_display = ('node', 'prerequisite')
    list_filter = ('node__roadmap',)
    search_fields = ('node__title', 'prerequisite__title')

    def save_model(self, request, obj, form, change):
        lock_roadmap_forest()
        require_write(request.user, obj, 'change' if obj.pk else 'add')
        obj.full_clean()
        obj.save()

"""Django admin definitions for Roadmap and Learning content."""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from mptt.admin import MPTTModelAdmin
from mptt.forms import TreeNodeChoiceField

from judge.models import Problem
from judge.utils.views import NoBatchDeleteMixin
from judge.widgets import AdminHeavySelect2Widget, AdminMartorWidget
from mentor.models import (
    LearningTopic, NodeProblem, Roadmap, RoadmapNode, RoadmapPrerequisite, TopicLesson,
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
    class Meta:
        model = LearningTopic
        fields = ('name', 'slug', 'status', 'visibility', 'organization', 'introduction')
        widgets = {'introduction': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('roadmap_markdown_preview')})}


class TopicLessonForm(PublicationControlFormMixin, forms.ModelForm):
    class Meta:
        model = TopicLesson
        fields = ('topic', 'title', 'slug', 'position', 'status', 'body')
        widgets = {'body': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('roadmap_markdown_preview')})}


class RoadmapNodeForm(PublicationControlFormMixin, forms.ModelForm):
    class Meta:
        model = RoadmapNode
        fields = ('roadmap', 'parent', 'type', 'title', 'slug', 'position',
                  'difficulty', 'status', 'learning_topic', 'is_optional_review')

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
        fields = ('node', 'prerequisite')

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


class TopicLessonInline(admin.StackedInline):
    model = TopicLesson
    form = TopicLessonForm
    extra = 0
    fields = ('title', 'slug', 'position', 'status', 'body')
    prepopulated_fields = {'slug': ('title',)}

    def get_formset(self, request, obj=None, **kwargs):
        FormSet = super().get_formset(request, obj, **kwargs)

        class TopicLessonFormSetWithUser(FormSet):
            def _construct_form(sub_self, i, **form_kwargs):
                form_kwargs['user'] = request.user
                return super()._construct_form(i, **form_kwargs)

        return TopicLessonFormSetWithUser

    def has_add_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.add_topiclesson') and request.user.has_perm('mentor.change_learningtopic'))

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.change_topiclesson') and request.user.has_perm('mentor.change_learningtopic'))

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and request.user.has_perm('mentor.delete_topiclesson') and request.user.has_perm('mentor.change_learningtopic'))


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
    list_display = ('title', 'slug', 'status', 'visibility', 'organization', 'get_node_count', 'tree_revision')
    list_filter = ('status', 'visibility', 'organization')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('tree_revision',)

    def get_node_count(self, obj):
        return obj.nodes.count()
    get_node_count.short_description = 'Nodes'

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)


@admin.register(LearningTopic)
class LearningTopicAdmin(RoadmapStaffAdmin):
    form = LearningTopicForm
    list_display = ('name', 'slug', 'status', 'visibility', 'organization', 'get_node_count', 'get_lesson_count', 'content_revision')
    list_filter = ('status', 'visibility', 'organization')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('content_revision', 'usage_warning')
    inlines = [TopicLessonInline]

    def get_node_count(self, obj):
        count = obj.roadmap_nodes.count()
        return format_html('{} nodes (SHARED)', count) if count > 1 else (f'{count} node' if count else '0 nodes')
    get_node_count.short_description = 'Placements'

    def get_lesson_count(self, obj):
        return obj.lessons.count()
    get_lesson_count.short_description = 'Lessons'

    def usage_warning(self, obj):
        if not obj or not obj.pk:
            return 'New topic (not yet referenced by any roadmap node).'
        nodes = list(obj.roadmap_nodes.select_related('roadmap').all())
        if not nodes:
            return 'Topic is not referenced by any roadmap node.'
        items = [format_html('<li>Roadmap: {} &rarr; Node: {} [{}]</li>', n.roadmap.title, n.title, n.status) for n in nodes]
        return format_html('Used by {} node(s):<ul>{}</ul>', len(nodes), mark_safe(''.join(items)))
    usage_warning.short_description = 'Topic Placements & Sharing Impact'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        topic = self.get_object(request, object_id)
        if topic and topic.roadmap_nodes.count() > 1:
            messages.warning(request, f'Topic "{topic.name}" is shared across {topic.roadmap_nodes.count()} nodes.')
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            if isinstance(obj, TopicLesson):
                lock_roadmap_forest()
                require_write(request.user, obj, 'delete')
                obj.delete()
            else:
                obj.delete()
        for instance in instances:
            if isinstance(instance, TopicLesson):
                if not instance.topic_id and form.instance.pk:
                    instance.topic = form.instance
                save_content(request.user, instance)
            else:
                instance.save()
        formset.save_m2m()


@admin.register(TopicLesson)
class TopicLessonAdmin(RoadmapStaffAdmin):
    form = TopicLessonForm
    list_display = ('title', 'topic', 'slug', 'position', 'status', 'content_revision')
    list_filter = ('status', 'topic')
    search_fields = ('title', 'slug', 'topic__name')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('content_revision',)

    def save_model(self, request, obj, form, change):
        save_content(request.user, obj)


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

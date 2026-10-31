"""Contextual staff authoring over the existing roadmap services and permissions."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from mentor.roadmap_models import (
    LearningTopic, NodeProblem, Publication, Roadmap, RoadmapNode,
    RoadmapPrerequisite, TopicLesson, lock_roadmap_forest,
)
from mentor.roadmap_services import (
    allowed_problem, delete_problem_link, require_write, save_content, save_node, save_problem_link,
)
from mentor.roadmap_workspace_forms import (
    PlacementForm, PrerequisiteLinkForm, ProblemLinkForm, PublicationForm,
    TopicIntroductionForm, unique_slug,
)


def _item_id(request):
    value = request.POST.get('item', '')
    if not value.isascii() or not value.isdigit() or int(value) <= 0:
        raise ValidationError('Chọn một mục hợp lệ trong danh sách.')
    return int(value)


def can_read(user, model):
    return bool(user.is_active and user.is_staff and (
        user.has_perm(f'mentor.view_{model._meta.model_name}') or
        user.has_perm(f'mentor.change_{model._meta.model_name}')))


def workspace_url(roadmap, node=None, tab=None):
    if node:
        url = reverse('admin:mentor_roadmap_node_workspace', args=[roadmap.pk, node.pk])
    else:
        url = reverse('admin:mentor_roadmap_workspace', args=[roadmap.pk])
    return url + (f'?tab={tab}' if tab else '')


def _shared_confirmation(request, topic):
    if topic and topic.roadmap_nodes.count() > 1 and request.POST.get('confirm_shared') != 'on':
        raise ValidationError('Nội dung đang dùng chung. Hãy xác nhận phạm vi ảnh hưởng trước khi lưu.')


def _reorder(user, queryset, item_id, direction, model):
    require_write(user, model(), 'change')
    items = list(queryset.order_by('position', 'pk'))
    index = next((i for i, item in enumerate(items) if str(item.pk) == str(item_id)), None)
    if index is None or direction not in ('up', 'down'):
        raise ValidationError('Mục cần sắp xếp không thuộc danh sách này.')
    destination = index + (-1 if direction == 'up' else 1)
    if not 0 <= destination < len(items):
        return
    items[index], items[destination] = items[destination], items[index]
    for position, item in enumerate(items):
        if item.position == position:
            continue
        item.position = position
        if isinstance(item, RoadmapNode):
            save_node(user, item)
        elif isinstance(item, TopicLesson):
            # Order is presentation, not a new content revision. Preserve reading/Q&A state.
            TopicLesson.objects.filter(pk=item.pk).update(position=position)
        else:
            save_problem_link(user, item)


@require_http_methods(['GET', 'HEAD', 'POST'])
def roadmap_workspace(request, roadmap_id, admin_site, node_id=None, adding=False):
    if not can_read(request.user, Roadmap) or not can_read(request.user, RoadmapNode):
        raise PermissionDenied
    roadmap = get_object_or_404(Roadmap, pk=roadmap_id)
    node = get_object_or_404(RoadmapNode.objects.select_related('learning_topic'), pk=node_id, roadmap=roadmap) if node_id else None
    kind = request.POST.get('kind', request.GET.get('kind', 'TOPIC'))
    if kind not in RoadmapNode.Type.values:
        raise Http404
    if adding:
        require_write(request.user, RoadmapNode(), 'add')
    tab = request.GET.get('tab', 'information')
    if tab not in ('information', 'lessons', 'problems', 'prerequisites', 'publication'):
        tab = 'information'
    errors = []
    bound_form = None
    action = request.POST.get('action') if request.method == 'POST' else None
    if request.method == 'POST':
        try:
            with transaction.atomic():
                lock_roadmap_forest()
                roadmap.refresh_from_db()
                if node:
                    node.refresh_from_db()
                if action == 'placement' and (node or adding):
                    require_write(request.user, RoadmapNode(), 'change' if node else 'add')
                    bound_form = PlacementForm(request.POST, roadmap=roadmap, node_type=kind,
                        user=request.user, instance=node)
                    if not bound_form.is_valid():
                        raise ValidationError('Thông tin chưa hợp lệ. Sửa các trường được đánh dấu bên dưới.')
                    item = bound_form.save(commit=False)
                    if not node:
                        item.position = (RoadmapNode.objects.filter(roadmap=roadmap, parent=item.parent)
                            .aggregate(last=Max('position'))['last'] or 0) + 1
                        if kind == RoadmapNode.Type.TOPIC:
                            if bound_form.cleaned_data.get('content_source') == 'reuse':
                                item.learning_topic = bound_form.cleaned_data['reuse_topic']
                            else:
                                require_write(request.user, LearningTopic(), 'add')
                                topic = LearningTopic(name=item.title[:100],
                                    slug=unique_slug(LearningTopic, item.title),
                                    visibility=roadmap.visibility, organization_id=roadmap.organization_id)
                                save_content(request.user, topic)
                                item.learning_topic = topic
                    save_node(request.user, item)
                    messages.success(request, 'Đã lưu nhóm / chuyên đề. Nội dung mới ở trạng thái Bản nháp.')
                    return HttpResponseRedirect(workspace_url(roadmap, item))
                elif action == 'introduction' and node and node.learning_topic_id:
                    require_write(request.user, node.learning_topic, 'change')
                    bound_form = TopicIntroductionForm(request.POST, instance=node.learning_topic)
                    if not bound_form.is_valid():
                        raise ValidationError('Giới thiệu chưa hợp lệ. Kiểm tra nội dung và xác nhận dùng chung.')
                    save_content(request.user, bound_form.save(commit=False))
                elif action == 'create_topic' and node and node.type == RoadmapNode.Type.TOPIC and not node.learning_topic_id:
                    require_write(request.user, node, 'change')
                    require_write(request.user, LearningTopic(), 'add')
                    node.learning_topic = save_content(request.user, LearningTopic(name=node.title[:100],
                        slug=unique_slug(LearningTopic, node.title), visibility=roadmap.visibility,
                        organization_id=roadmap.organization_id))
                    save_node(request.user, node)
                elif action == 'problem_add' and node:
                    require_write(request.user, node, 'change')
                    bound_form = ProblemLinkForm(request.POST, user=request.user, instance=NodeProblem(node=node))
                    if not bound_form.is_valid():
                        raise ValidationError('Chọn một bài luyện hợp lệ và chưa được gắn ở đây.')
                    link = bound_form.save(commit=False)
                    link.position = (node.problem_links.aggregate(last=Max('position'))['last'] or 0) + 10
                    save_problem_link(request.user, link)
                elif action == 'problem_remove' and node:
                    link = get_object_or_404(NodeProblem, pk=_item_id(request), node=node)
                    delete_problem_link(request.user, link)
                elif action == 'prerequisite_add' and node:
                    require_write(request.user, node, 'change')
                    require_write(request.user, RoadmapPrerequisite(), 'add')
                    bound_form = PrerequisiteLinkForm(request.POST, node=node)
                    if not bound_form.is_valid():
                        raise ValidationError('Quan hệ học trước chưa hợp lệ. Không được tự phụ thuộc, trùng hoặc tạo vòng.')
                    link = bound_form.save(commit=False)
                    link.full_clean()
                    link.save()
                elif action == 'prerequisite_remove' and node:
                    require_write(request.user, node, 'change')
                    link = get_object_or_404(RoadmapPrerequisite, pk=_item_id(request), node=node)
                    require_write(request.user, link, 'delete')
                    link.delete()
                elif action == 'reorder' and node:
                    target = request.POST.get('target')
                    if target == 'node':
                        require_write(request.user, node, 'change')
                        queryset, model = RoadmapNode.objects.filter(roadmap=roadmap, parent_id=node.parent_id), RoadmapNode
                        item_id = node.pk
                    elif target == 'problem':
                        require_write(request.user, node, 'change')
                        queryset, model = node.problem_links.all(), NodeProblem
                        item_id = request.POST.get('item')
                    elif target == 'lesson' and node.learning_topic_id:
                        require_write(request.user, node.learning_topic, 'change')
                        _shared_confirmation(request, node.learning_topic)
                        queryset, model = node.learning_topic.lessons.all(), TopicLesson
                        item_id = request.POST.get('item')
                    else:
                        raise ValidationError('Danh sách cần sắp xếp không hợp lệ.')
                    _reorder(request.user, queryset, item_id, request.POST.get('direction'), model)
                elif action == 'publication':
                    bound_form = PublicationForm(request.POST, node=node)
                    if not bound_form.is_valid():
                        raise ValidationError('Chọn phạm vi và xác nhận trước khi đổi trạng thái.')
                    if not request.user.has_perm('mentor.publish_roadmap'):
                        raise PermissionDenied
                    target = bound_form.cleaned_data['target']
                    if target == 'topic':
                        if node is None or not node.learning_topic_id:
                            raise ValidationError('Chuyên đề chưa có bộ nội dung.')
                        _shared_confirmation(request, node.learning_topic)
                        obj = node.learning_topic
                    elif target == 'node' and node is not None:
                        obj = node
                    elif target == 'roadmap' and node is None:
                        obj = roadmap
                    else:
                        raise ValidationError('Phạm vi xuất bản không hợp lệ.')
                    require_write(request.user, obj, 'change')
                    obj.status = bound_form.cleaned_data['status']
                    if isinstance(obj, RoadmapNode):
                        save_node(request.user, obj)
                    else:
                        save_content(request.user, obj)
                else:
                    raise ValidationError('Thao tác không hợp lệ trong ngữ cảnh hiện tại.')
            messages.success(request, 'Đã lưu thay đổi.')
            return HttpResponseRedirect(workspace_url(roadmap, node, tab))
        except ValidationError as exc:
            errors = exc.messages
            if node:
                node.refresh_from_db()
            roadmap.refresh_from_db()
    nodes = list(roadmap.nodes.select_related('learning_topic').annotate(
        problem_count=Count('problem_links', distinct=True),
        lesson_count=Count('learning_topic__lessons', distinct=True)).order_by('tree_id', 'lft'))
    tree = []
    by_id = {}
    for item in nodes:
        entry = {'node': item, 'children': [], 'url': workspace_url(roadmap, item)}
        by_id[item.pk] = entry
        if item.parent_id in by_id:
            by_id[item.parent_id]['children'].append(entry)
        else:
            tree.append(entry)
    topic = node.learning_topic if node and node.learning_topic_id else None
    can_topic = can_read(request.user, LearningTopic)
    can_lesson = can_read(request.user, TopicLesson)
    placements = list(topic.roadmap_nodes.select_related('roadmap')) if topic and can_topic else []
    lessons = list(topic.lessons.order_by('position', 'pk')) if topic and can_topic and can_lesson else []
    problems = []
    if node:
        for link in node.problem_links.select_related('problem').order_by('position', 'pk'):
            try:
                allowed_problem(request.user, link.problem_id)
            except ValidationError:
                problems.append({'link': link, 'accessible': False})
            else:
                problems.append({'link': link, 'accessible': True})
    prerequisites = list(node.prerequisites.select_related('prerequisite')) if node else []
    dependents = list(RoadmapPrerequisite.objects.filter(prerequisite=node).select_related('node')) if node else []
    form = (bound_form if action == 'placement' else PlacementForm(roadmap=roadmap, instance=node,
        node_type=kind, user=request.user,
        initial={'parent': request.GET.get('parent')} if adding else None)) if node or adding else None
    intro_form = (bound_form if action == 'introduction' else TopicIntroductionForm(instance=topic)) if topic and can_topic and tab == 'information' else None
    problem_form = (bound_form if action == 'problem_add' else ProblemLinkForm(user=request.user)) if node and tab == 'problems' else None
    prereq_form = (bound_form if action == 'prerequisite_add' else PrerequisiteLinkForm(node=node)) if node else None
    publish_form = bound_form if action == 'publication' else PublicationForm(node=node)
    from mentor.roadmap_staff_preview import get_roadmap_visibility
    visibility = get_roadmap_visibility(roadmap, node=node, topic=topic)
    context = {**admin_site.each_context(request), 'title': ('Thêm nhóm' if kind == 'GROUP' else 'Thêm chuyên đề') if adding else (node.title if node else roadmap.title),
        'opts': Roadmap._meta, 'roadmap': roadmap, 'node': node, 'tree': tree, 'nodes': nodes,
        'adding': adding, 'kind': kind, 'tab': tab, 'errors': errors, 'placement_form': form,
        'intro_form': intro_form, 'problem_form': problem_form, 'prereq_form': prereq_form,
        'publish_form': publish_form, 'topic': topic if can_topic else None,
        'has_topic': bool(topic), 'can_topic': can_topic, 'can_lesson': can_lesson,
        'lessons': lessons, 'problems': problems, 'prerequisites': prerequisites,
        'dependents': dependents, 'placements': placements, 'shared': len(placements) > 1,
        'visibility_report': visibility, 'workspace_url': workspace_url(roadmap, node),
        'descendant_count': node.get_descendant_count() if node else len(nodes),
        'media': sum((f.media for f in (form, intro_form, problem_form, prereq_form) if f), forms_media()),
    }
    return TemplateResponse(request, 'admin/mentor/roadmap/workspace.html', context)


def forms_media():
    from django.forms import Media
    return Media()

"""Read-only staff preview of roadmap learner-facing content."""
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.template.response import TemplateResponse
from django.urls import reverse

from judge.models import Problem

from .models import LearningTopic, Roadmap, RoadmapNode, TopicLesson
from .roadmap_models import Publication, Visibility


def get_roadmap_visibility(roadmap, node=None, topic=None, lesson=None):
    """Report known publication blockers; audience scope is not learner access."""
    reasons = []
    if roadmap.status != Publication.PUBLISHED:
        reasons.append('Lộ trình đang ở trạng thái bản nháp.')
    if node is not None and node.roadmap_id != roadmap.pk:
        reasons.append('Chủ đề thuộc một lộ trình khác.')
    if node is not None:
        for ancestor in node.get_ancestors():
            if ancestor.status != Publication.PUBLISHED:
                reasons.append(f'Chủ đề cha “{ancestor.title}” đang ở trạng thái bản nháp.')
        if node.status != Publication.PUBLISHED:
            reasons.append('Chủ đề đang ở trạng thái bản nháp.')
    if topic is None and lesson is not None:
        topic = lesson.topic
    if topic is None and node is not None:
        topic = node.learning_topic
    if (topic is None and node is not None and node.type == RoadmapNode.Type.TOPIC
            and not node.problem_links.exists()):
        reasons.append('Chuyên đề chưa có bộ nội dung hoặc bài luyện để mở trang học.')
    if topic is not None:
        if node is not None and node.learning_topic_id != topic.pk:
            reasons.append('Chuyên đề không phải chuyên đề được liên kết với chủ đề đã chọn.')
        # Public topics may be used on organization roadmaps; organization topics
        # must match the roadmap's organization scope.
        if topic.visibility == Visibility.ORGANIZATION and (
                roadmap.visibility != Visibility.ORGANIZATION or
                topic.organization_id != roadmap.organization_id):
            reasons.append('Phạm vi tổ chức của chuyên đề không khớp với lộ trình.')
        if topic.status != Publication.PUBLISHED:
            reasons.append('Chuyên đề đang ở trạng thái bản nháp.')
        has_intro = bool(topic.introduction.strip())
        has_published_lesson = any(
            item.body.strip() for item in topic.lessons.filter(status=Publication.PUBLISHED))
        has_linked_problems = node.problem_links.exists() if node is not None else False
        if not (has_intro or has_published_lesson or has_linked_problems):
            reasons.append('Chuyên đề chưa có phần giới thiệu, bài giảng đã xuất bản hoặc bài tập liên kết.')
    if lesson is not None:
        if topic is not None and lesson.topic_id != topic.pk:
            reasons.append('Bài giảng thuộc một chuyên đề khác.')
        if lesson.status != Publication.PUBLISHED:
            reasons.append('Bài giảng đang ở trạng thái bản nháp.')
        if not lesson.body.strip():
            reasons.append('Bài giảng chưa có nội dung.')
    return {'visible': not reasons, 'reasons': reasons}


def _has_view_or_change(model_admin, request, obj):
    return model_admin and (model_admin.has_view_permission(request, obj) or
                            model_admin.has_change_permission(request, obj))

def _markdown(value):
    from .lesson_visuals import render_lesson_markdown
    return render_lesson_markdown(value or '')


def roadmap_staff_preview(request, roadmap_id, admin_site):
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    if not (request.user.is_authenticated and request.user.is_active and request.user.is_staff):
        raise PermissionDenied

    roadmap_admin = admin_site._registry.get(Roadmap)
    node_admin = admin_site._registry.get(RoadmapNode)
    topic_admin = admin_site._registry.get(LearningTopic)
    lesson_admin = admin_site._registry.get(TopicLesson)
    if not _has_view_or_change(roadmap_admin, request, None):
        raise PermissionDenied
    try:
        roadmap = Roadmap.objects.get(pk=roadmap_id)
    except Roadmap.DoesNotExist:
        raise Http404

    node = None
    topic = None
    lesson = None
    node_id = request.GET.get('node')
    lesson_id = request.GET.get('lesson')
    if node_id:
        try:
            node = RoadmapNode.objects.select_related('learning_topic').get(pk=node_id)
        except (RoadmapNode.DoesNotExist, ValueError):
            raise Http404
        if node.roadmap_id != roadmap.pk:
            raise Http404
        if not _has_view_or_change(node_admin, request, node):
            raise PermissionDenied
        topic = node.learning_topic
        if topic is not None and not _has_view_or_change(topic_admin, request, topic):
            raise PermissionDenied
    if lesson_id:
        try:
            lesson = TopicLesson.objects.select_related('topic').get(pk=lesson_id)
        except (TopicLesson.DoesNotExist, ValueError):
            raise Http404
        if node is None or topic is None or lesson.topic_id != topic.pk:
            raise Http404
        if not _has_view_or_change(lesson_admin, request, lesson):
            raise PermissionDenied

    nodes = [candidate for candidate in RoadmapNode.objects.filter(roadmap=roadmap)
             .order_by('tree_id', 'lft') if _has_view_or_change(node_admin, request, candidate)]
    lessons = ([candidate for candidate in TopicLesson.objects.filter(topic=topic).order_by('position', 'pk')
                if _has_view_or_change(lesson_admin, request, candidate)] if topic else [])
    rendered_lesson = {
        'body_html': _markdown(lesson.body),
        'summary_html': _markdown(lesson.summary),
    } if lesson else None

    problem_rows = []
    hidden_problem_count = 0
    if node is not None:
        links = list(node.problem_links.select_related('problem').order_by('position', 'pk'))
        accessible_ids = set(Problem.get_visible_problems(request.user).filter(
            pk__in=[link.problem_id for link in links]).values_list('pk', flat=True))
        for link in links:
            problem = link.problem
            if problem.pk in accessible_ids and problem.is_accessible_by(request.user):
                problem_rows.append({'name': problem.translated_name(request.LANGUAGE_CODE),
                                     'url': reverse('problem_detail', args=[problem.code])})
            else:
                hidden_problem_count += 1

    visibility = get_roadmap_visibility(roadmap, node=node, topic=topic, lesson=lesson)
    context = {
        **admin_site.each_context(request),
        'title': f'Xem trước: {lesson.title if lesson else node.title if node else roadmap.title}',
        'roadmap': roadmap,
        'node': node,
        'nodes': nodes,
        'topic': topic,
        'lessons': lessons,
        'lesson': lesson,
        'rendered_lesson': rendered_lesson,
        'roadmap_intro_html': _markdown(roadmap.introduction),
        'topic_intro_html': _markdown(topic.introduction) if topic else '',
        'visibility_report': visibility,
        'problem_rows': problem_rows,
        'hidden_problem_count': hidden_problem_count,
        'workspace_url': reverse('admin:mentor_roadmap_workspace', args=[roadmap.pk]),
        'node_workspace_url': (reverse('admin:mentor_roadmap_node_workspace', args=[roadmap.pk, node.pk])
                               if node else None),
        'is_draft_preview': (roadmap.status != Publication.PUBLISHED or
                             (node is not None and node.status != Publication.PUBLISHED) or
                             (topic is not None and topic.status != Publication.PUBLISHED) or
                             (lesson is not None and lesson.status != Publication.PUBLISHED)),
        'audience_label': ('Công khai' if roadmap.visibility == Visibility.PUBLIC else 'Trong tổ chức'),
    }
    response = TemplateResponse(request, 'admin/mentor/roadmap/preview.html', context)
    response['Cache-Control'] = 'private, no-store'
    return response

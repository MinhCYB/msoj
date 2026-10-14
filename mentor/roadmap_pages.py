"""HTML adapters over the authorized Roadmap read selectors."""
from urllib.parse import urlencode

from django.http import Http404, HttpResponseBadRequest, HttpResponseBase
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from .roadmap_explorer import build_roadmap_explorer
from .roadmap_selectors import (
    TreeRevisionStale, get_accessible_roadmap, get_accessible_roadmaps,
)

def wants_html(request):
    return request.GET.get('format') != 'json' and 'text/html' in request.headers.get('Accept', '')


def private_page(request, template, context, status=200):
    response = render(request, template, context, status=status)
    response['Cache-Control'] = 'private, no-store'
    response['Vary'] = 'Accept'
    return response


def roadmap_index(request):
    return private_page(request, 'roadmap/index.html', {
        'title': 'Lộ trình', 'roadmaps': get_accessible_roadmaps(request.user),
    })


def roadmap_map(request, slug):
    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        raise Http404

    try:
        explorer_result = build_roadmap_explorer(request, roadmap)
        if isinstance(explorer_result, HttpResponseBase):
            return explorer_result
    except TreeRevisionStale:
        return private_page(request, 'roadmap/stale.html', {
            'title': 'Lộ trình đã thay đổi', 'roadmap': roadmap,
        }, status=409)

    explorer = explorer_result['explorer']
    focus = explorer_result['focus']
    breadcrumb = explorer_result['breadcrumb']
    map_url = explorer_result['map_url']
    title = explorer_result['title']

    return private_page(request, 'roadmap/map.html', {
        'title': title,
        'roadmap': roadmap,
        'explorer': explorer,
        'map_url': map_url,
        'focus': focus,
        'breadcrumb': breadcrumb,
        'nodes': explorer['visible_nodes'],
    })


def roadmap_learning_page(request, roadmap, data, lesson=None):
    node = data['node']
    map_url = reverse('roadmap_detail', args=[roadmap.slug])
    context = {
        'title': lesson['lesson']['title'] if lesson else node['title'],
        'roadmap': roadmap,
        'learning': data,
        'lesson_data': lesson,
        'map_url': map_url,
        'return_url': f"{map_url}?focus={node['id']}",
        'learn_url': reverse('roadmap_node_learn', args=[roadmap.slug, node['id']]),
    }
    if lesson:
        context['lecture_state'] = lesson.get('lecture_state')
    else:
        context['resume_lesson_url'] = data.get('resume_lesson_url')
    return private_page(request, 'roadmap/lesson.html' if lesson else 'roadmap/learn.html', context)


def roadmap_markdown_preview(request):
    if not (request.user.is_active and request.user.is_staff and any(
        request.user.has_perm(f'mentor.{action}_{model}')
        for model in ('learningtopic', 'topiclesson')
        for action in ('add', 'change')
    )):
        raise PermissionDenied
    if request.method != 'POST':
        return private_page(request, 'roadmap/preview.html', {'preview_data': ''}, status=405)
    if 'content' not in request.POST:
        return HttpResponseBadRequest('No preview data specified.')
    return private_page(request, 'roadmap/preview.html', {'preview_data': request.POST['content']})

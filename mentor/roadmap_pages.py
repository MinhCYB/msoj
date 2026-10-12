"""HTML adapters over the authorized Roadmap read selectors."""
from urllib.parse import urlencode

from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from .roadmap_selectors import (
    TreeRevisionStale, serialize_node_list, get_accessible_roadmap,
    get_accessible_roadmaps, get_effective_published_node,
    get_node_immediate_children, get_roadmap_roots,
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
    focus = None
    cursor = request.GET.get('cursor')
    try:
        focus_id = request.GET.get('focus')
        limit = int(request.GET.get('limit', 50))
        if limit < 1:
            raise ValueError
        limit = min(100, limit)
        if focus_id is not None:
            focus = get_effective_published_node(roadmap, int(focus_id))
            if focus is None:
                raise Http404
        if focus:
            focus.has_children = focus.children.filter(status='PUBLISHED').exists()
            nodes = serialize_node_list(roadmap, [focus], request.user)
            children, next_cursor = get_node_immediate_children(roadmap, focus, request.user, cursor, limit)
        else:
            nodes, next_cursor = get_roadmap_roots(roadmap, request.user, cursor, limit)
            children = []
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Tham số lộ trình không hợp lệ.')
    except TreeRevisionStale:
        return private_page(request, 'roadmap/stale.html', {
            'title': 'Lộ trình đã thay đổi', 'roadmap': roadmap,
        }, status=409)
    map_url = reverse('roadmap_detail', args=[slug])
    query = {'cursor': next_cursor} if next_cursor else {}
    if focus:
        query['focus'] = focus.pk
    return private_page(request, 'roadmap/map.html', {
        'title': roadmap.title, 'roadmap': roadmap, 'nodes': nodes,
        'focus': focus, 'breadcrumb': list(focus.get_ancestors(include_self=True)) if focus else [],
        'children': children, 'next_cursor': next_cursor,
        'next_url': map_url + '?' + urlencode(query) if next_cursor else None,
        'map_url': map_url,
    })


def roadmap_learning_page(request, roadmap, data, lesson=None):
    node = data['node']
    map_url = reverse('roadmap_detail', args=[roadmap.slug])
    return private_page(request, 'roadmap/lesson.html' if lesson else 'roadmap/learn.html', {
        'title': lesson['lesson']['title'] if lesson else node['title'],
        'roadmap': roadmap, 'learning': data, 'lesson_data': lesson,
        'map_url': map_url, 'return_url': f"{map_url}?focus={node['id']}",
        'learn_url': reverse('roadmap_node_learn', args=[roadmap.slug, node['id']]),
    })


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

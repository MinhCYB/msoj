"""Views for Mentor Roadmap v2 Phase 1 read APIs.

Provides JSON endpoints with explicit allowlists, private no-store headers,
keyset pagination with signed cursors, and strict authorization.
"""
import json

from .lecture_services import LectureQAError, execute_lesson_qa, update_lesson_reading_state
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

from .roadmap_pages import roadmap_index, roadmap_map, roadmap_learning_page, wants_html
from .roadmap_selectors import (
    TreeRevisionStale,
    get_accessible_roadmap,
    get_accessible_roadmaps,
    get_effective_published_node,
    get_node_immediate_children,
    get_node_readiness,
    get_node_document_lessons,
    get_node_learn_data,
    get_node_lesson_data,
    get_progress_data,
    get_roadmap_roots,
)


def _json_response(data, status=200):
    """Construct JsonResponse with private no-store Cache-Control header."""
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    response['Vary'] = 'Accept'
    return response


def _parse_limit(request):
    """Extract and validate limit query parameter, default 50, cap 100."""
    limit_raw = request.GET.get('limit')
    if limit_raw is None:
        return 50
    try:
        limit = int(limit_raw)
        if limit < 1:
            raise ValueError
        return min(limit, 100)
    except (ValueError, TypeError) as e:
        raise ValueError('Invalid limit parameter: must be a positive integer') from e


def _parse_focus_id(request):
    """Extract and validate focus query parameter."""
    focus_raw = request.GET.get('focus')
    if focus_raw is None:
        return None
    try:
        return int(focus_raw)
    except (ValueError, TypeError) as e:
        raise ValueError('Invalid focus parameter: must be an integer') from e


def roadmap_list_view(request):
    """
    GET /roadmaps/
    List published roadmaps accessible to the current user.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)
    if wants_html(request):
        return roadmap_index(request)

    roadmaps = get_accessible_roadmaps(request.user)
    data = [
        {
            'id': r.id,
            'slug': r.slug,
            'title': r.title,
            'introduction': r.introduction,
            'tree_revision': r.tree_revision,
            'visibility': r.visibility,
            'url': reverse('roadmap_detail', args=[r.slug]),
        }
        for r in roadmaps
    ]
    return _json_response({'roadmaps': data})


def roadmap_detail_view(request, slug):
    """
    GET /roadmap/<slug>/
    Retrieve roadmap details, optional focus node metadata, and keyset-paginated root nodes.
    Supports ?focus=<node_id>, ?cursor=<cursor>, ?limit=<n>.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)
    if wants_html(request):
        return roadmap_map(request, slug)

    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        return _json_response({'error': 'Roadmap not found or unauthorized'}, status=404)

    try:
        focus_id = _parse_focus_id(request)
        limit = _parse_limit(request)
    except ValueError as e:
        return _json_response({'error': str(e)}, status=400)

    focus_metadata = None
    if focus_id is not None:
        focus_node = get_effective_published_node(roadmap, focus_id)
        if focus_node is None:
            return _json_response({'error': 'Focus node not found or unauthorized'}, status=404)

        ancestors = list(focus_node.get_ancestors(include_self=True))
        content_state, learn_url = get_node_readiness(roadmap, focus_node, request.user)
        focus_metadata = {
            'id': focus_node.id,
            'title': focus_node.title,
            'slug': focus_node.slug,
            'type': focus_node.type,
            'difficulty': focus_node.difficulty,
            'content_state': content_state,
            'learn_url': learn_url,
            'breadcrumb': [
                {
                    'id': a.id,
                    'title': a.title,
                    'slug': a.slug,
                    'focus_url': f"{reverse('roadmap_detail', args=[roadmap.slug])}?focus={a.id}",
                }
                for a in ancestors
            ],
        }

    cursor_str = request.GET.get('cursor')
    try:
        items, next_cursor = get_roadmap_roots(roadmap, request.user, cursor_str=cursor_str, limit=limit)
    except TreeRevisionStale:
        return _json_response(
            {'error': 'Stale tree revision; refresh branch', 'tree_revision': roadmap.tree_revision},
            status=409,
        )
    except ValueError as e:
        return _json_response({'error': str(e)}, status=400)

    return _json_response({
        'roadmap': {
            'id': roadmap.id,
            'slug': roadmap.slug,
            'title': roadmap.title,
            'introduction': roadmap.introduction,
            'tree_revision': roadmap.tree_revision,
            'visibility': roadmap.visibility,
        },
        'focus': focus_metadata,
        'items': items,
        'next_cursor': next_cursor,
        'tree_revision': roadmap.tree_revision,
    })


def roadmap_node_children_view(request, slug, node_id):
    """
    GET /roadmap/<slug>/nodes/<id>/children/
    Retrieve immediate children of node with signed keyset pagination cursor.
    Supports ?cursor=<cursor>, ?limit=<n>.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)

    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        return _json_response({'error': 'Roadmap not found or unauthorized'}, status=404)

    parent_node = get_effective_published_node(roadmap, node_id)
    if parent_node is None:
        return _json_response({'error': 'Parent node not found or unauthorized'}, status=404)

    try:
        limit = _parse_limit(request)
    except ValueError as e:
        return _json_response({'error': str(e)}, status=400)

    cursor_str = request.GET.get('cursor')
    try:
        items, next_cursor = get_node_immediate_children(
            roadmap, parent_node, request.user, cursor_str=cursor_str, limit=limit
        )
    except TreeRevisionStale:
        return _json_response(
            {'error': 'Stale tree revision; refresh branch', 'tree_revision': roadmap.tree_revision},
            status=409,
        )
    except ValueError as e:
        return _json_response({'error': str(e)}, status=400)

    return _json_response({
        'items': items,
        'next_cursor': next_cursor,
        'tree_revision': roadmap.tree_revision,
    })


def roadmap_node_learn_view(request, slug, node_id):
    """
    GET /roadmap/<slug>/nodes/<id>/learn/
    Retrieve learning content for node: topic introduction, lesson list, and canonical problem links.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)

    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        return _json_response({'error': 'Roadmap not found or unauthorized'}, status=404)

    learn_data = get_node_learn_data(roadmap, node_id, request.user)
    if learn_data is None:
        return _json_response({'error': 'Learning content not found or unauthorized'}, status=404)

    if wants_html(request):
        documents, resume_lesson_id = get_node_document_lessons(roadmap, node_id, request.user)
        learn_data['document_lessons'] = documents
        learn_data['resume_lesson_id'] = resume_lesson_id
        return roadmap_learning_page(request, roadmap, learn_data)

    return _json_response(learn_data)


def roadmap_node_lesson_view(request, slug, node_id, lesson_id):
    """
    GET /roadmap/<slug>/nodes/<id>/lessons/<lesson_id>/
    Retrieve theory lesson markdown body and navigation for node's learning topic.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)

    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        return _json_response({'error': 'Roadmap not found or unauthorized'}, status=404)

    lesson_data = get_node_lesson_data(roadmap, node_id, lesson_id, request.user)
    if lesson_data is None:
        return _json_response({'error': 'Lesson not found or unauthorized'}, status=404)

    if wants_html(request):
        response = HttpResponseRedirect(
            f"{reverse('roadmap_node_learn', args=[roadmap.slug, node_id])}#rm-lesson-{lesson_id}"
        )
        response['Cache-Control'] = 'private, no-store'
        response['Vary'] = 'Accept'
        return response

    return _json_response(lesson_data)


def roadmap_node_lesson_questions_view(request, slug, node_id, lesson_id):
    """
    POST /roadmap/<slug>/nodes/<id>/lessons/<lesson_id>/questions/
    Contextual theory lesson Q&A via AI Gateway with strict reviewed output.
    """
    if request.method != 'POST':
        return _json_response({'error': 'method_not_allowed'}, status=405)

    if not request.user.is_authenticated:
        return _json_response({'error': 'access_denied'}, status=401)

    if len(request.body) > 16384:
        return _json_response({'error': 'bad_request'}, status=400)

    try:
        body = json.loads(request.body)
    except (TypeError, ValueError):
        return _json_response({'error': 'bad_request'}, status=400)

    if not isinstance(body, dict) or not set(body.keys()).issubset({'question', 'content_revision', 'section'}):
        return _json_response({'error': 'bad_request'}, status=400)

    question = body.get('question')
    content_revision = body.get('content_revision')
    section = body.get('section')

    try:
        result = execute_lesson_qa(
            request.user, slug, node_id, lesson_id, question, content_revision, section=section
        )
        return _json_response(result)
    except LectureQAError as exc:
        return _json_response({'error': exc.code}, status=exc.status_code)


def roadmap_node_lesson_state_view(request, slug, node_id, lesson_id):
    """
    POST /roadmap/<slug>/nodes/<id>/lessons/<lesson_id>/state/
    Persist normalized reading scroll offset (0..10000) pinned to content revision.
    """
    if request.method != 'POST':
        return _json_response({'error': 'method_not_allowed'}, status=405)

    if not request.user.is_authenticated:
        return _json_response({'error': 'access_denied'}, status=401)

    if len(request.body) > 16384:
        return _json_response({'error': 'bad_request'}, status=400)

    try:
        body = json.loads(request.body)
    except (TypeError, ValueError):
        return _json_response({'error': 'bad_request'}, status=400)

    if not isinstance(body, dict) or not set(body.keys()).issubset({'offset', 'content_revision', 'position_version'}):
        return _json_response({'error': 'bad_request'}, status=400)

    offset = body.get('offset')
    content_revision = body.get('content_revision')

    try:
        result = update_lesson_reading_state(
            request.user, slug, node_id, lesson_id, offset, content_revision, body.get('position_version')
        )
        return _json_response(result)
    except LectureQAError as exc:
        return _json_response({'error': exc.code}, status=exc.status_code)

def roadmap_progress_view(request, slug):
    """
    GET /roadmap/<slug>/progress/?focus=<node_id>
    Retrieve user's distinct AC progress for the entire roadmap or a focused subtree.
    """
    if request.method != 'GET':
        return _json_response({'error': 'Method not allowed'}, status=405)

    roadmap = get_accessible_roadmap(request.user, slug)
    if roadmap is None:
        return _json_response({'error': 'Roadmap not found or unauthorized'}, status=404)

    try:
        focus_id = _parse_focus_id(request)
    except ValueError as e:
        return _json_response({'error': str(e)}, status=400)

    progress_data = get_progress_data(roadmap, request.user, focus_node_id=focus_id)
    if progress_data is None:
        return _json_response({'error': 'Focus node not found or unauthorized'}, status=404)

    return _json_response(progress_data)

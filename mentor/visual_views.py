"""Bounded, stateless compilation endpoint for learner visual input edits."""
import json

from django.http import JsonResponse

from .visual_documents import compile_document

MAX_REQUEST_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def compile_visual_view(request):
    if request.method != 'POST':
        response = JsonResponse({'error': 'POST required'}, status=405)
        response['Allow'] = 'POST'
        return response
    if len(request.body) > MAX_REQUEST_BYTES:
        return JsonResponse({'error': 'Visual input exceeds 128 KiB'}, status=413)
    try:
        raw = json.loads(request.body, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        if not isinstance(raw, dict) or set(raw) != {'document', 'input'}:
            raise ValueError('Expected {document, input}')
        document = raw['document']
        if not isinstance(document, dict) or not isinstance(document.get('timeline'), dict) or 'generator' not in document['timeline']:
            raise ValueError('Only built-in generator documents can be recompiled')
        if not isinstance(raw['input'], dict):
            raise ValueError('Input must be an object')
        document = dict(document)
        timeline = dict(document['timeline'])
        timeline['input'] = raw['input']
        document['timeline'] = timeline
        compiled = compile_document(document)
        encoded = json.dumps(compiled, ensure_ascii=False, separators=(',', ':'))
        if len(encoded.encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ValueError('Compiled payload exceeds 2 MiB')
    except (ValueError, TypeError, RecursionError) as exc:
        return JsonResponse({'error': str(exc) or 'Invalid visual document'}, status=400)
    response = JsonResponse(compiled)
    response['Cache-Control'] = 'no-store'
    return response


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'Non-finite JSON number {value} is not allowed')

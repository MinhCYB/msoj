"""Bounded, declarative lesson visualizations. Database content is never executable."""
import json
import re
import uuid

from django.core.exceptions import ValidationError
from django.utils.html import format_html
from lxml import html
from markupsafe import Markup

from judge.jinja2.markdown import markdown
from .visual_documents import compile_document, validate_document

MAX_BLOCKS = 12
MAX_CONFIG_LENGTH = 128 * 1024
MAX_TOTAL_CONFIG_LENGTH = 512 * 1024
FENCE = re.compile(r'^(`{3,})[ \t]*([^`]*?)[ \t]*$')


def validate_visual(config):
    """Validate and normalize a v2 declarative document."""
    return validate_document(config)


def visual_blocks(content):
    """Recognize root-level fences while honoring enclosing ordinary fences."""
    lines = content.splitlines(keepends=True)
    offset = 0
    opened = None
    body = []
    for line in lines:
        stripped = line.rstrip('\r\n')
        match = FENCE.fullmatch(stripped)
        if opened is None:
            if match:
                opened = (offset, match[1], match[2])
                body = []
        elif re.fullmatch(re.escape(opened[1]) + r'[ \t]*', stripped):
            if opened[2] == 'msoj-visual':
                yield opened[0], offset + len(line), ''.join(body)
            opened = None
        else:
            body.append(line)
        offset += len(line)
    if opened and opened[2] == 'msoj-visual':
        yield opened[0], len(content), None


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'Non-finite JSON number: {value}')


def _parse(raw):
    if raw is None:
        raise ValueError('Khối msoj-visual chưa có hàng đóng bằng dấu backtick.')
    if len(raw.encode('utf-8')) > MAX_CONFIG_LENGTH:
        raise ValueError('Cấu hình trực quan vượt giới hạn 128 KiB.')
    try:
        config = json.loads(raw, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise ValueError('Cấu hình trực quan phải là JSON hợp lệ, không lặp khóa hoặc số vô hạn.') from None
    return validate_visual(config)


def validate_visual_blocks(content):
    total = 0
    for index, (_, _, raw) in enumerate(visual_blocks(content), 1):
        if index > MAX_BLOCKS:
            raise ValidationError('Mỗi bài giảng chỉ nhận tối đa 12 khối trực quan.')
        try:
            _parse(raw)
            total += len(raw.encode('utf-8'))
            if total > MAX_TOTAL_CONFIG_LENGTH:
                raise ValueError('Tổng cấu hình trực quan vượt giới hạn 512 KiB.')
        except ValueError as exc:
            raise ValidationError(f'Khối trực quan {index}: {exc}') from None
def _fallback(compiled):
    doc = compiled['document']
    content = [format_html('<p>{}</p>', doc['summary'])]
    for name, value in doc['data'].items():
        content.append(format_html('<h4>{}</h4>', name))
        if value['type'] == 'sequence':
            content.append(format_html('<p>{}</p>', ', '.join(str(v) for v in value['values']) or 'Dữ liệu rỗng.'))
        elif value['type'] == 'table':
            headers = Markup('').join(format_html('<th>{}</th>', column['id']) for column in value['columns'])
            rows = [format_html('<tr>{}</tr>', headers)]
            for row in value['rows']:
                cells = Markup('').join(format_html('<td>{}</td>', row[column['id']]) for column in value['columns'])
                rows.append(format_html('<tr>{}</tr>', cells))
            content.append(format_html('<table><tbody>{}</tbody></table>', Markup('').join(rows)))
        elif value['type'] == 'graph':
            nodes = Markup('').join(format_html('<li>{}</li>', node.get('label', node['id'])) for node in value['nodes'])
            edges = ', '.join(f'{edge["from"]}–{edge["to"]}' for edge in value['edges'])
            content.extend((format_html('<ul>{}</ul>', nodes), format_html('<p>Edges: {}</p>', edges or 'none')))
        elif value['type'] == 'matrix':
            rows = []
            for row in value['values']:
                cells = Markup('').join(format_html('<td>{}</td>', cell) for cell in row)
                rows.append(format_html('<tr>{}</tr>', cells))
            content.append(format_html('<table><tbody>{}</tbody></table>', Markup('').join(rows)))
        elif value['type'] == 'map':
            entries = Markup('').join(format_html('<li>{}: {}</li>', entry['key'], entry['value']) for entry in value['entries'])
            content.append(format_html('<ul>{}</ul>', entries))
        elif value['type'] == 'variables':
            scopes = Markup('').join(format_html('<li>{}: {}</li>', scope['name'], ', '.join(frame['procedure'] for frame in scope['frames'])) for scope in value['scopes'])
            content.append(format_html('<ul>{}</ul>', scopes))
        elif value['type'] == 'scene':
            descriptions = []
            for primitive in value['primitives']:
                if primitive['type'] in ('point', 'circle'):
                    detail = f'{primitive["type"]} {primitive["id"]} at ({primitive["x"]}, {primitive["y"]})'
                elif primitive['type'] in ('segment', 'arrow'):
                    detail = f'{primitive["type"]} {primitive["id"]} from ({primitive["x1"]}, {primitive["y1"]}) to ({primitive["x2"]}, {primitive["y2"]})'
                elif primitive['type'] == 'rect':
                    detail = f'rect {primitive["id"]} at ({primitive["x"]}, {primitive["y"]}), {primitive["width"]}×{primitive["height"]}'
                else:
                    detail = f'text {primitive["id"]} at ({primitive["x"]}, {primitive["y"]}): {primitive["text"]}'
                descriptions.append(format_html('<li>{}</li>', detail + (f' — {primitive["label"]}' if primitive.get('label') else '')))
            content.append(format_html('<ul>{}</ul>', Markup('').join(descriptions)))
    return Markup('').join(content)
def render_lesson_markdown(content):
    replacements = {}
    pieces = []
    previous = 0
    for index, (start, end, raw) in enumerate(visual_blocks(content), 1):
        token = 'MSOJVISUAL' + uuid.uuid4().hex
        pieces.extend((content[previous:start], '\n\n' + token + '\n\n'))
        previous = end
        try:
            if index > MAX_BLOCKS:
                raise ValueError('Mỗi bài giảng chỉ nhận tối đa 12 khối trực quan.')
            compiled = compile_document(_parse(raw))
            total = sum(len(item.encode('utf-8')) for _, _, item in visual_blocks(content) if item is not None)
            if total > MAX_TOTAL_CONFIG_LENGTH:
                raise ValueError('Tổng cấu hình trực quan vượt giới hạn 512 KiB.')
            payload = json.dumps(compiled, ensure_ascii=False, separators=(',', ':'))
            doc = compiled['document']
            fallback = _fallback(compiled)
            replacement = format_html('<section class="msoj-visual" data-visual-config="{}" aria-label="{}"><h3>{}</h3><p>{}</p><div class="mv-static-fallback">{}</div></section>', payload, doc['title'], doc['title'], doc['summary'], fallback)
        except ValueError as exc:
            replacement = format_html('<p class="mv-error" role="status">Không mở được mô phỏng: {}</p>', str(exc))
        replacements[token] = str(replacement)
    if not replacements:
        return markdown(content, 'default')
    pieces.append(content[previous:])
    tree = html.fragment_fromstring(str(markdown(''.join(pieces), 'default')), create_parent='div')
    for paragraph in list(tree.iter('p')):
        if len(paragraph) == 0 and paragraph.text in replacements:
            replacement = html.fragment_fromstring(replacements[paragraph.text])
            replacement.tail = paragraph.tail
            paragraph.getparent().replace(paragraph, replacement)
    return Markup(''.join(html.tostring(child, encoding='unicode') for child in tree))

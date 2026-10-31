"""Strict validation and compilation for declarative visual documents v2."""
import copy
import json
import math
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

GENERATORS = {'for-loop', 'bfs', 'dfs', 'matrix-chain', 'dp-bitmask-matching'}
SCHEMA_PATH = Path(__file__).with_name('visual_schema_v2.json')


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _fail(path, message):
    raise ValueError(f'{path}: {message}')


def _walk(value, depth=0, active=None):
    active = set() if active is None else active
    if depth > 20:
        raise ValueError('document: nesting exceeds 20 levels')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('document: numbers must be finite')
    if isinstance(value, (dict, list)):
        marker = id(value)
        if marker in active:
            raise ValueError('document: cyclic object graph is not valid JSON')
        active.add(marker)
        for item in value.values() if isinstance(value, dict) else value:
            _walk(item, depth + 1, active)
        active.remove(marker)


def _unique(items, path):
    ids = [item if isinstance(item, str) else item['id'] for item in items]
    if len(ids) != len(set(ids)):
        _fail(path, 'IDs must be unique')
    return set(ids)


def _validate_generator(kind, input_data):
    def integer(value, low, high):
        return type(value) is int and low <= value <= high
    if not isinstance(input_data, dict):
        _fail('timeline.input', 'must be an object')
    if kind == 'for-loop':
        if set(input_data) != {'start', 'end', 'step'} or not integer(input_data.get('start'), -10, 20) or not integer(input_data.get('end'), -10, 20) or not integer(input_data.get('step'), 1, 5):
            _fail('timeline.input', 'invalid for-loop bounds')
        if input_data['start'] <= input_data['end'] and (input_data['end'] - input_data['start']) // input_data['step'] + 1 > 31:
            _fail('timeline.input', 'more than 31 iterations')
    elif kind in {'bfs', 'dfs'}:
        n = input_data.get('n')
        if set(input_data) != {'n', 'edges', 'source'} or not integer(n, 1, 8) or not integer(input_data.get('source'), 0, n - 1) or not isinstance(input_data['edges'], list):
            _fail('timeline.input', 'invalid graph input')
        edges = set()
        for edge in input_data['edges']:
            if not isinstance(edge, list) or len(edge) != 2 or any(not integer(v, 0, n - 1) for v in edge) or edge[0] == edge[1]:
                _fail('timeline.input.edges', 'invalid edge')
            pair = tuple(sorted(edge))
            if pair in edges:
                _fail('timeline.input.edges', 'duplicate edge')
            edges.add(pair)
    elif kind == 'matrix-chain':
        dims = input_data.get('dimensions')
        if set(input_data) != {'dimensions'} or not isinstance(dims, list) or not 2 <= len(dims) <= 7 or any(not integer(v, 1, 50) for v in dims):
            _fail('timeline.input', 'invalid matrix-chain dimensions')
    elif kind == 'dp-bitmask-matching':
        matrix = input_data.get('matrix')
        if set(input_data) != {'matrix'} or not isinstance(matrix, list) or not 1 <= len(matrix) <= 5 or any(not isinstance(row, list) or len(row) != len(matrix) or any(type(v) is not int or v not in (0, 1) for v in row) for row in matrix):
            _fail('timeline.input', 'expected square binary matrix')
    else:
        _fail('timeline.generator', 'unknown generator')


def _validate_bindings(bindings, data, controls, module_ids):
    arity = {'select': 2, 'lookup': 2, 'slice': 3, 'length': 1, 'sum': 1, 'prefix-sum': 1, 'range-sum': 3, 'scene-point': 4, 'add': 2, 'subtract': 2, 'multiply': 2, 'difference': 2}
    binding_ids = {item['id'] for item in bindings}
    control_ids = {item['id'] for item in controls}
    refs = set(data) | control_ids | binding_ids
    controls_by_id = {item['id']: item for item in controls}
    numeric_bindings = {item['id'] for item in bindings if item['operation'] in {'length', 'sum', 'range-sum', 'add', 'subtract', 'multiply', 'difference'}}
    numeric_operands = {item['id'] for item in controls if item['type'] == 'number'} | numeric_bindings
    graph, intervals, sequence_bounds = {}, {}, {}

    def bounded(value, path):
        if (type(value) is int and abs(value) > 1e12) or (type(value) is float and (not math.isfinite(value) or abs(value) > 1e12)):
            _fail(path, 'numeric values must be finite and have absolute value at most 1e12')

    for name, item in data.items():
        if item['type'] == 'sequence':
            values = item['values']
            for value in values:
                if type(value) in (int, float):
                    bounded(value, f'data.{name}')
            bound = sum(abs(value) for value in values if type(value) in (int, float))
            if not math.isfinite(bound):
                _fail(f'data.{name}', 'numeric sum may overflow')
            sequence_bounds[name] = bound
        elif item['type'] == 'matrix':
            values = [value for row in item['values'] for value in row]
        elif item['type'] == 'table':
            values = [row[column['id']] for row in item['rows'] for column in item['columns'] if column['type'] == 'number']
        elif item['type'] == 'map':
            values = [entry['value'] for entry in item['entries']]
        else:
            values = []
        for value in values:
            if type(value) in (int, float):
                bounded(value, f'data.{name}')
    for control in controls:
        if control['type'] == 'number':
            for field in ('min', 'max', 'value'):
                bounded(control[field], f'controls.{control["id"]}.{field}')
            intervals[control['id']] = (control['min'], control['max'])

    for binding in bindings:
        op, args, bid = binding['operation'], binding['args'], binding['id']
        if binding['target'] not in module_ids or len(args) != arity[op]:
            _fail(f'bindings.{bid}', 'invalid target or operation arity')
        if op == 'select':
            if args[0] not in control_ids or args[1] not in data:
                _fail(f'bindings.{bid}.args', 'select requires [controlId,dataId]')
        elif op == 'scene-point':
            if args[0] not in data or data[args[0]]['type'] != 'scene':
                _fail(f'bindings.{bid}', 'scene-point requires scene data')
            points = {item['id']: item for item in data[args[0]]['primitives']}
            if args[1] not in points or points[args[1]]['type'] != 'point' or any(arg not in controls_by_id or controls_by_id[arg]['type'] != 'number' for arg in args[2:]):
                _fail(f'bindings.{bid}', 'scene-point requires a point and numeric controls')
            point = points[args[1]]
            if point.get('xControl') != args[2] or point.get('yControl') != args[3]:
                _fail(f'bindings.{bid}', 'point control IDs do not match binding')
        else:
            if any(arg not in refs for arg in args):
                _fail(f'bindings.{bid}.args', 'unknown operand ID')
            if op in {'length', 'sum', 'prefix-sum', 'slice', 'range-sum'} and (args[0] not in data or data[args[0]]['type'] != 'sequence'):
                _fail(f'bindings.{bid}', 'operation requires sequence data')
            if op in {'sum', 'prefix-sum', 'range-sum'} and any(type(value) not in (int, float) for value in data[args[0]]['values']):
                _fail(f'bindings.{bid}', 'operation requires numeric values')
            if op == 'lookup' and (args[0] not in data or data[args[0]]['type'] != 'map'):
                _fail(f'bindings.{bid}', 'lookup requires map data')
            if op in {'slice', 'range-sum'} and any(arg not in numeric_operands for arg in args[1:]):
                _fail(f'bindings.{bid}', 'range arguments must be numeric')
            if op in {'add', 'subtract', 'multiply', 'difference'} and any(arg not in numeric_operands for arg in args):
                _fail(f'bindings.{bid}', 'arithmetic operands must be numeric')
        graph[bid] = [arg for arg in args if arg in binding_ids]

    visiting, depths = set(), {}
    def visit(node):
        if node in visiting:
            _fail('bindings', 'derived dependency cycle')
        if node in depths:
            return depths[node]
        visiting.add(node)
        depth = 1 + max((visit(child) for child in graph[node]), default=0)
        visiting.remove(node)
        if depth > 8:
            _fail('bindings', 'dependency depth exceeds 8')
        depths[node] = depth
        return depth
    for node in graph:
        visit(node)

    binding_by_id = {binding['id']: binding for binding in bindings}
    def interval_for(bid):
        if bid in intervals:
            return intervals[bid]
        op, args = binding_by_id[bid]['operation'], binding_by_id[bid]['args']
        if op in {'length', 'sum', 'range-sum'}:
            if op == 'length':
                result = (len(data[args[0]]['values']),) * 2
            else:
                result = (-sequence_bounds[args[0]], sequence_bounds[args[0]])
        elif op in {'add', 'subtract', 'multiply', 'difference'}:
            left, right = (interval_for(arg) for arg in args)
            if op == 'add':
                result = (left[0] + right[0], left[1] + right[1])
            elif op in {'subtract', 'difference'}:
                result = (left[0] - right[1], left[1] - right[0])
            else:
                products = (left[0] * right[0], left[0] * right[1], left[1] * right[0], left[1] * right[1])
                result = (min(products), max(products))
        else:
            return (-1e12, 1e12)
        if any(not math.isfinite(value) for value in result):
            _fail(f'bindings.{bid}', 'numeric operation may overflow')
        bounded(result[0], f'bindings.{bid}')
        bounded(result[1], f'bindings.{bid}')
        intervals[bid] = result
        return result
    for bid in numeric_bindings:
        interval_for(bid)
def _validate_authored(steps, data, controls):
    state = copy.deepcopy(data)
    _unique(steps, 'timeline.steps')
    controls_by_id = {item['id']: item for item in controls}
    control_ids = set(controls_by_id)
    for step in steps:
        op, targets = step['operation'], step['targets']
        if op == 'reset':
            if targets:
                _fail(f'timeline.steps.{step["id"]}', 'reset takes no targets')
            state = copy.deepcopy(data)
            continue
        if op == 'set-control':
            if len(targets) != 1 or targets[0] not in control_ids:
                _fail(f'timeline.steps.{step["id"]}', 'invalid control target')
            control = controls_by_id[targets[0]]
            value = step.get('value')
            if 'value' not in step or (control['type'] == 'number' and (type(value) not in (int, float) or not control['min'] <= value <= control['max'])) or (control['type'] == 'boolean' and type(value) is not bool) or (control['type'] == 'select' and value not in [option['value'] for option in control['options']]):
                _fail(f'timeline.steps.{step["id"]}', 'invalid control value')
            continue
        if op == 'clear-selection':
            if targets:
                _fail(f'timeline.steps.{step["id"]}', 'clear-selection takes no targets')
            continue
        if op == 'select':
            if not targets or targets[0] not in state:
                _fail(f'timeline.steps.{step["id"]}', 'selection requires a data target')
            selected = targets[1] if len(targets) > 1 else targets[0]
            target_data = state[targets[0]]
            valid_ids = set()
            if target_data['type'] == 'sequence':
                valid_ids.update(target_data['itemIds'])
            elif target_data['type'] == 'map':
                valid_ids.update(entry['id'] for entry in target_data['entries'])
            elif target_data['type'] == 'table':
                valid_ids.update(row['id'] for row in target_data['rows'])
            elif target_data['type'] == 'graph':
                valid_ids.update(node['id'] for node in target_data['nodes'])
                valid_ids.update(edge['id'] for edge in target_data['edges'])
            elif target_data['type'] == 'scene':
                valid_ids.update(item['id'] for item in target_data['primitives'])
            if len(targets) > 1 and selected not in valid_ids:
                _fail(f'timeline.steps.{step["id"]}', 'unknown selection item ID')
            continue
        arity = {'set-item': 2, 'insert': 1, 'remove': 2, 'enqueue': 1, 'dequeue': 1, 'push': 1, 'pop': 1, 'map-set': 1, 'map-delete': 1, 'matrix-set': 1}
        if len(targets) != arity[op] or targets[0] not in state:
            _fail(f'timeline.steps.{step["id"]}', 'invalid target')
        target = state[targets[0]]
        typ = target['type']
        if op in {'set-item', 'insert', 'remove', 'enqueue', 'dequeue', 'push', 'pop'} and typ != 'sequence' or op in {'map-set', 'map-delete'} and typ != 'map' or op == 'matrix-set' and typ != 'matrix':
            _fail(f'timeline.steps.{step["id"]}', 'operation/data type mismatch')
        if op in {'set-item', 'remove'}:
            if targets[1] not in target['itemIds']:
                _fail(f'timeline.steps.{step["id"]}', 'unknown item ID')
            index = target['itemIds'].index(targets[1])
            if op == 'remove':
                target['values'].pop(index); target['itemIds'].pop(index)
            else:
                target['values'][index] = step['value']
        elif op == 'insert':
            index, item = step['index'], step['item']
            if index > len(target['values']) or len(target['values']) >= 256 or item['id'] in target['itemIds']:
                _fail(f'timeline.steps.{step["id"]}', 'invalid insert')
            target['values'].insert(index, item['value']); target['itemIds'].insert(index, item['id'])
        elif op in {'enqueue', 'push'}:
            item_id = step['id'][:59] + '-item'
            if len(target['values']) >= 256 or item_id in target['itemIds']:
                _fail(f'timeline.steps.{step["id"]}', 'sequence full or item ID duplicate')
            target['values'].append(step['value']); target['itemIds'].append(item_id)
        elif op in {'dequeue', 'pop'}:
            if not target['values']:
                _fail(f'timeline.steps.{step["id"]}', 'cannot remove from empty sequence')
            index = 0 if op == 'dequeue' else -1
            target['values'].pop(index); target['itemIds'].pop(index)
        elif op == 'matrix-set':
            matrix = target['values']
            if step['row'] >= len(matrix) or step['column'] >= (len(matrix[0]) if matrix else 0):
                _fail(f'timeline.steps.{step["id"]}', 'matrix index out of range')
            matrix[step['row']][step['column']] = step['value']
        elif op == 'map-set':
            entries, entry = target['entries'], step['entry']
            if any(old['id'] == entry['id'] and old['key'] != entry['key'] for old in entries):
                _fail(f'timeline.steps.{step["id"]}', 'duplicate map entry ID')
            index = next((i for i, old in enumerate(entries) if old['key'] == entry['key']), None)
            if index is None and len(entries) >= 256:
                _fail(f'timeline.steps.{step["id"]}', 'map full')
            if index is None:
                entries.append(copy.deepcopy(entry))
            else:
                entries[index] = copy.deepcopy(entry)
        elif op == 'map-delete':
            if step['entryId'] not in {entry['id'] for entry in target['entries']}:
                _fail(f'timeline.steps.{step["id"]}', 'unknown map entry')
            target['entries'] = [entry for entry in target['entries'] if entry['id'] != step['entryId']]


def _semantic(doc):
    data, modules = doc['data'], doc['modules']
    controls, bindings = doc.get('controls', []), doc.get('bindings', [])
    _unique(list(data) + modules + controls + bindings, 'document')
    for name, item in data.items():
        typ = item['type']
        if typ == 'sequence' and 'itemIds' in item and (len(item['itemIds']) != len(item['values']) or len(set(item['itemIds'])) != len(item['itemIds'])):
            _fail(f'data.{name}.itemIds', 'must uniquely identify sequence values')
        if typ == 'table':
            columns = [column['id'] for column in item['columns']]
            _unique(columns, f'data.{name}.columns'); _unique(item['rows'], f'data.{name}.rows')
            for row in item['rows']:
                if set(row) != {'id', *columns}:
                    _fail(f'data.{name}.rows', 'row fields must exactly match declared columns')
                for column in item['columns']:
                    value = row[column['id']]
                    if column['type'] == 'string' and not isinstance(value, str) or column['type'] == 'number' and type(value) not in (int, float) or column['type'] == 'boolean' and type(value) is not bool:
                        _fail(f'data.{name}.rows.{row["id"]}.{column["id"]}', 'column value type mismatch')
        if typ == 'graph':
            nodes = _unique(item['nodes'], f'data.{name}.nodes'); _unique(item['edges'], f'data.{name}.edges'); seen = set()
            for edge in item['edges']:
                if edge['from'] not in nodes or edge['to'] not in nodes or edge['from'] == edge['to']:
                    _fail(f'data.{name}.edges.{edge["id"]}', 'invalid endpoints')
                key = (edge['from'], edge['to']) if edge.get('directed') else tuple(sorted((edge['from'], edge['to'])))
                if key in seen:
                    _fail(f'data.{name}.edges.{edge["id"]}', 'duplicate edge')
                seen.add(key)
        if typ == 'matrix':
            rows = item['values']; width = len(rows[0]) if rows else 0
            if any(len(row) != width for row in rows):
                _fail(f'data.{name}.values', 'matrix must be rectangular')
            if 'rowLabels' in item and len(item['rowLabels']) != len(rows) or 'columnLabels' in item and len(item['columnLabels']) != width:
                _fail(f'data.{name}', 'matrix label count mismatch')
        if typ == 'map':
            _unique(item['entries'], f'data.{name}.entries')
            keys = [(type(entry['key']).__name__, json.dumps(entry['key'], sort_keys=True)) for entry in item['entries']]
            if len(keys) != len(set(keys)):
                _fail(f'data.{name}.entries', 'duplicate map key')
        if typ == 'variables':
            _unique(item['scopes'], f'data.{name}.scopes')
            _unique([frame for scope in item['scopes'] for frame in scope['frames']], f'data.{name}.frames')
        if typ == 'scene':
            _unique(item['primitives'], f'data.{name}.primitives')
            for primitive in item['primitives']:
                if primitive['type'] == 'rect' and (primitive['x'] + primitive['width'] > item['width'] or primitive['y'] + primitive['height'] > item['height']):
                    _fail(f'data.{name}.primitives.{primitive["id"]}', 'rectangle outside scene')
                if primitive['type'] == 'circle' and (primitive['x'] + primitive['radius'] > item['width'] or primitive['y'] + primitive['radius'] > item['height']):
                    _fail(f'data.{name}.primitives.{primitive["id"]}', 'circle outside scene')
    module_ids = {module['id'] for module in modules}
    expected = {'vector': {'sequence'}, 'queue': {'sequence'}, 'stack': {'sequence'}, 'table': {'table'}, 'chart': {'table'}, 'graph': {'graph'}, 'tree': {'graph'}, 'matrix': {'matrix'}, 'map': {'map'}, 'set': {'map'}, 'hash-table': {'map'}, 'variables': {'variables'}, 'call-stack': {'variables'}, 'scene': {'scene'}, 'number-line': {'sequence', 'matrix'}}
    for module in modules:
        kind, source = module['type'], module.get('source')
        if kind in expected and (source not in data or data[source]['type'] not in expected[kind]):
            _fail(f'modules.{module["id"]}.source', 'missing or incompatible source')
        if kind == 'chart':
            fields = {column['id']: column['type'] for column in data[source]['columns']}
            if module['x'] not in fields or module['y'] not in fields:
                _fail(f'modules.{module["id"]}', 'unknown chart field')
            if fields[module['y']] != 'number' or module['kind'] == 'scatter' and fields[module['x']] != 'number':
                _fail(f'modules.{module["id"]}', 'chart axes must be numeric')
        if kind == 'code':
            languages = [source['language'] for source in module['sources']]
            if len(languages) != len(set(languages)):
                _fail(f'modules.{module["id"]}.sources', 'languages must be unique')
            for source in module['sources']:
                if len(source['lineIds']) != max(1, len(source['sourceCode'].splitlines())) or len(set(source['lineIds'])) != len(source['lineIds']):
                    _fail(f'modules.{module["id"]}.sources', 'one unique ID per source line required')
        if kind in {'formula', 'explanation'}:
            for token in module.get('tokens', module.get('content')):
                if token['type'] == 'value' and token['source'] not in set(data) | {control['id'] for control in controls} | {binding['id'] for binding in bindings}:
                    _fail(f'modules.{module["id"]}', 'unknown value token source')
    areas = doc['layout']['areas']; width = len(areas[0])
    if width > 4 or any(len(row) != width for row in areas):
        _fail('layout.areas', 'must be rectangular with at most four columns')
    positions = {module_id: [] for module_id in module_ids}
    for row_index, row in enumerate(areas):
        for column_index, module_id in enumerate(row):
            if module_id == '_':
                continue
            if module_id not in positions:
                _fail(f'layout.areas[{row_index}][{column_index}]', 'unknown module')
            positions[module_id].append((row_index, column_index))
    for module_id, cells in positions.items():
        if not cells:
            _fail('layout.areas', f'module {module_id} is not placed')
        rows = range(min(r for r, _ in cells), max(r for r, _ in cells) + 1)
        cols = range(min(c for _, c in cells), max(c for _, c in cells) + 1)
        if set(cells) != {(r, c) for r in rows for c in cols}:
            _fail('layout.areas', f'module {module_id} area is not rectangular')
    if len(doc['layout']['readingOrder']) != len(module_ids) or set(doc['layout']['readingOrder']) != module_ids:
        _fail('layout.readingOrder', 'must contain each module once')
    for control in controls:
        if control['type'] == 'number' and (type(control['value']) not in (int, float) or control['min'] > control['value'] or control['value'] > control['max'] or control['max'] - control['min'] > 100000):
            _fail(f'controls.{control["id"]}', 'invalid numeric range')
        if control['type'] == 'boolean' and type(control['value']) is not bool:
            _fail(f'controls.{control["id"]}', 'expected boolean value')
        if control['type'] == 'select' and control['value'] not in [option['value'] for option in control['options']]:
            _fail(f'controls.{control["id"]}', 'value is not a declared option')
    _validate_bindings(bindings, data, controls, module_ids)
    timeline = doc.get('timeline')
    if timeline and 'generator' in timeline:
        _validate_generator(timeline['generator'], timeline['input'])
    elif timeline:
        line_ids = {line_id for module in doc['modules'] if module['type'] == 'code' for source in module['sources'] for line_id in source['lineIds']}
        for step in timeline['steps']:
            if any(line_id not in line_ids for line_id in step.get('lines', [])):
                _fail(f'timeline.steps.{step["id"]}.lines', 'unknown code line ID')
        _validate_authored(timeline['steps'], data, controls)


def validate_document(config):
    if not isinstance(config, dict):
        raise ValueError('document must be an object')
    _walk(config)
    errors = sorted(_validator().iter_errors(config), key=lambda error: (list(map(str, error.absolute_path)), error.message))
    if errors:
        error = errors[0]
        _fail('.'.join(map(str, error.absolute_path)) or 'document', error.message)
    document = copy.deepcopy(config)
    for value in document['data'].values():
        if value['type'] == 'sequence':
            value.setdefault('itemIds', [f'item-{i}' for i in range(len(value['values']))])
    _semantic(document)
    return document


def _frame(data, title, text, highlights=None, lines=None, output=None):
    frame = {'data': copy.deepcopy(data), 'title': title, 'text': text, 'highlights': highlights or {}}
    if lines is not None:
        frame['lines'] = lines if isinstance(lines, list) else [lines]
    if output is not None:
        frame['output'] = output
    return frame


def _authored(document):
    state = copy.deepcopy(document['data'])
    controls = {control['id']: control['value'] for control in document.get('controls', [])}
    frames = [_frame(state, document['title'], document['summary'])]
    selection = None
    frames[0]['controls'] = copy.deepcopy(controls)
    frames[0]['selection'] = None
    for step in document['timeline']['steps']:
        op, targets = step['operation'], step['targets']
        target = targets[0] if targets else None
        if op == 'reset':
            state = copy.deepcopy(document['data'])
            controls = {control['id']: control['value'] for control in document.get('controls', [])}
            selection = None
        elif op == 'set-control':
            controls[target] = step['value']
        elif op == 'select':
            selection = {'dataId': target, 'id': targets[1] if len(targets) > 1 else target}
        elif op == 'clear-selection':
            selection = None
        elif op == 'set-item':
            state[target]['values'][state[target]['itemIds'].index(targets[1])] = step['value']
        elif op == 'insert':
            state[target]['values'].insert(step['index'], step['item']['value']); state[target]['itemIds'].insert(step['index'], step['item']['id'])
        elif op == 'remove':
            index = state[target]['itemIds'].index(targets[1]); state[target]['values'].pop(index); state[target]['itemIds'].pop(index)
        elif op in {'enqueue', 'push'}:
            state[target]['values'].append(step['value']); state[target]['itemIds'].append(step['id'][:59] + '-item')
        elif op in {'dequeue', 'pop'}:
            index = 0 if op == 'dequeue' else -1; state[target]['values'].pop(index); state[target]['itemIds'].pop(index)
        elif op == 'map-set':
            entries, entry = state[target]['entries'], step['entry']; index = next((i for i, item in enumerate(entries) if item['key'] == entry['key']), None)
            if index is None: entries.append(copy.deepcopy(entry))
            else: entries[index] = copy.deepcopy(entry)
        elif op == 'map-delete':
            state[target]['entries'] = [item for item in state[target]['entries'] if item['id'] != step['entryId']]
        elif op == 'matrix-set':
            state[target]['values'][step['row']][step['column']] = step['value']
        highlights = {'targets': targets}
        if op in {'set-item', 'remove'}:
            highlights['items'] = {target: [targets[1]]}
        elif op == 'insert':
            highlights['items'] = {target: [step['item']['id']]}
        elif op in {'enqueue', 'push'}:
            highlights['items'] = {target: [step['id'][:59] + '-item']}
        elif op == 'map-set':
            highlights['items'] = {target: [step['entry']['id']]}
        elif op == 'map-delete':
            highlights['items'] = {target: [step['entryId']]}
        elif op == 'matrix-set':
            highlights['cells'] = {target: [[step['row'], step['column']]]}
        frames.append(_frame(state, step['id'], step['explanation'], highlights, step.get('lines')))
        frames[-1]['controls'] = copy.deepcopy(controls)
        frames[-1]['selection'] = copy.deepcopy(selection)
    for frame in frames:
        _validate_bindings(document.get('bindings', []), frame['data'], document.get('controls', []), {module['id'] for module in document['modules']})
    return frames


def compile_document(config):
    document = validate_document(config)
    timeline = document.get('timeline')
    if not timeline:
        frames = [_frame(document['data'], document['title'], document['summary'])]
    elif 'generator' in timeline:
        from .visual_algorithms import algorithm_document, compile_algorithm
        kind, input_data = timeline['generator'], timeline['input']
        generated_doc = algorithm_document(kind, input_data, document['id'])
        generated_data = generated_doc['data']
        generated_code = next(module for module in generated_doc['modules'] if module['type'] == 'code')
        for module in document['modules']:
            if module['type'] == 'code' and module['id'] == generated_code['id']:
                module['sources'] = copy.deepcopy(generated_code['sources'])
        # Keep authored modules/layout while refreshing generated source datasets.
        merged = copy.deepcopy(document['data'])
        for name, generated in generated_data.items():
            if name in merged and merged[name]['type'] != generated['type']:
                _fail(f'data.{name}', 'generated source type collides with authored data')
            merged[name] = copy.deepcopy(generated)
        document['data'] = merged
        for control in document.get('controls', []):
            key = control.get('inputKey')
            if key in input_data:
                control['value'] = input_data[key]
        document = validate_document(document)
        frames = compile_algorithm(kind, input_data)
        for frame in frames:
            frame['data'] = {**copy.deepcopy(merged), **frame['data']}
            _validate_bindings(document.get('bindings', []), frame['data'], document.get('controls', []), {module['id'] for module in document['modules']})
    else:
        frames = _authored(document)
    if len(frames) > 500:
        _fail('timeline', 'more than 500 snapshots')
    size = 0
    for frame in frames:
        size += len(json.dumps(frame, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        if size > 2 * 1024 * 1024:
            _fail('timeline', 'snapshot budget exceeds 2 MiB')
    return {'document': document, 'frames': frames}


def convert_legacy(config):
    if not isinstance(config, dict) or type(config.get('version')) is not int or config.get('version') != 1 or set(config) - {'type', 'version', 'input', 'allow_input_edit'}:
        raise ValueError('unsupported legacy visualization')
    kind, input_data = config.get('type'), config.get('input')
    if kind not in GENERATORS:
        raise ValueError('unsupported legacy visualization')
    _validate_generator(kind, input_data)
    from .visual_algorithms import algorithm_document
    return validate_document(algorithm_document(kind, input_data, f'legacy-{kind}'))

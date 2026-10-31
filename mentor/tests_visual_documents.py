from django.test import SimpleTestCase

from .visual_algorithms import algorithm_document
from .visual_documents import compile_document, convert_legacy, validate_document


def static_document(data, module_type, source, **module_options):
    module = {'id': 'view', 'type': module_type, 'source': source, 'caption': 'Readable view', **module_options}
    return {'version': 2, 'id': 'sample', 'title': 'Sample', 'summary': 'A readable equivalent.', 'data': data,
            'modules': [module], 'layout': {'areas': [['view']], 'readingOrder': ['view']}}


def algorithm_config(kind, input_data):
    document = algorithm_document(kind, input_data, 'sample')
    return document


class VisualDocumentTests(SimpleTestCase):
    def test_static_document_compiles_one_accessible_snapshot(self):
        config = static_document({'values': {'type': 'sequence', 'values': [1, 2]}}, 'vector', 'values')
        compiled = compile_document(config)
        self.assertEqual(len(compiled['frames']), 1)
        self.assertEqual(compiled['frames'][0]['text'], config['summary'])
        self.assertEqual(compiled['document']['data']['values']['itemIds'], ['item-0', 'item-1'])
        self.assertNotIn('timeline', compiled['document'])

    def test_table_rows_must_exactly_match_declared_columns(self):
        config = static_document({'table': {'type': 'table', 'columns': [{'id': 'count', 'type': 'number'}], 'rows': [{'id': 'r', 'count': 1, 'extra': 2}]}}, 'table', 'table')
        with self.assertRaises(ValueError):
            validate_document(config)

    def test_boolean_is_not_integer_in_generator_inputs(self):
        config = algorithm_config('for-loop', {'start': 1, 'end': 3, 'step': 1})
        config['timeline']['input'] = {'start': True, 'end': 2, 'step': 1}
        with self.assertRaises(ValueError):
            compile_document(config)

    def test_derived_dependency_cycle_is_rejected_after_operand_validation(self):
        config = static_document({'values': {'type': 'sequence', 'values': [1]}}, 'vector', 'values')
        config['controls'] = [{'id': 'number', 'type': 'number', 'label': 'Number', 'min': 0, 'max': 10, 'step': 1, 'value': 1}]
        config['bindings'] = [
            {'id': 'first', 'operation': 'add', 'args': ['number', 'second'], 'target': 'view'},
            {'id': 'second', 'operation': 'add', 'args': ['number', 'first'], 'target': 'view'},
        ]
        with self.assertRaises(ValueError):
            validate_document(config)

    def test_scene_geometry_bounds_are_validated(self):
        config = static_document({'drawing': {'type': 'scene', 'width': 20, 'height': 20, 'primitives': [{'id': 'box', 'type': 'rect', 'x': 10, 'y': 10, 'width': 15, 'height': 2}]}}, 'scene', 'drawing')
        with self.assertRaises(ValueError):
            validate_document(config)

    def test_authored_sequence_operations_use_stable_ids_and_snapshots(self):
        config = static_document({'values': {'type': 'sequence', 'values': [4]}}, 'vector', 'values')
        config['timeline'] = {'steps': [
            {'id': 'insert-step', 'operation': 'insert', 'targets': ['values'], 'index': 1, 'item': {'id': 'new-item', 'value': 9}, 'explanation': 'Insert item.'},
            {'id': 'remove-step', 'operation': 'remove', 'targets': ['values', 'item-0'], 'explanation': 'Remove first.'},
        ]}
        frames = compile_document(config)['frames']
        self.assertEqual(frames[1]['data']['values']['values'], [4, 9])
        self.assertEqual(frames[1]['data']['values']['itemIds'], ['item-0', 'new-item'])
        self.assertEqual(frames[2]['data']['values']['values'], [9])
        self.assertEqual(frames[1]['data']['values']['values'], [4, 9])

    def test_for_loop_zero_iterations_still_checks_and_prints_zero(self):
        frames = compile_document(algorithm_config('for-loop', {'start': 4, 'end': 1, 'step': 2}))['frames']
        self.assertEqual(frames[-2]['output'], '0\n')
        locals_ = frames[-3]['data']['variables']['scopes'][0]['frames'][0]['locals']
        self.assertEqual(locals_['i'], 4)

    def test_bfs_marks_when_enqueued_and_leaves_unreachable_null(self):
        frames = compile_document(algorithm_config('bfs', {'n': 4, 'edges': [[0, 2], [0, 1]], 'source': 0}))['frames']
        self.assertEqual(frames[-1]['data']['dist']['values'], [0, 1, 1, None])
        nodes = frames[-1]['data']['graph']['nodes']
        self.assertEqual([node['id'] for node in nodes], ['v0', 'v1', 'v2', 'v3'])

    def test_recursive_dfs_frames_are_real_call_stack(self):
        frames = compile_document(algorithm_config('dfs', {'n': 3, 'edges': [[0, 1], [1, 2]], 'source': 0}))['frames']
        nested = [frame for frame in frames if len(frame['data']['callstack']['scopes'][0]['frames']) == 3]
        self.assertTrue(nested)
        self.assertEqual(nested[0]['data']['callstack']['scopes'][0]['frames'][-1]['procedure'], 'dfs')

    def test_matrix_chain_cost_example(self):
        frames = compile_document(algorithm_config('matrix-chain', {'dimensions': [10, 20, 5, 30]}))['frames']
        self.assertEqual(frames[-1]['data']['cost']['values'][0][2], 2500)

    def test_matching_is_bitmask_dp_and_return_is_not_stdout(self):
        result = compile_document(algorithm_config('dp-bitmask-matching', {'matrix': [[1, 0], [0, 1]]}))
        self.assertEqual(result['frames'][-1]['data']['dp']['values'][-1], 1)
        self.assertNotIn('output', result['frames'][-1])

    def test_legacy_conversion_is_separate_and_preserves_generator_input(self):
        legacy = {'type': 'for-loop', 'version': 1, 'input': {'start': 1, 'end': 3, 'step': 1}}
        result = convert_legacy(legacy)
        self.assertEqual(result['version'], 2)
        self.assertEqual(result['timeline']['input'], legacy['input'])
        self.assertEqual(result['modules'][0]['type'], 'variables')

    def test_authored_controls_and_selection_rewind_on_reset(self):
        config = static_document({'values': {'type': 'sequence', 'values': [4]}}, 'vector', 'values')
        config['controls'] = [{'id': 'amount', 'type': 'number', 'label': 'Amount', 'min': 0, 'max': 10, 'step': 1, 'value': 2}]
        config['timeline'] = {'steps': [
            {'id': 'change', 'operation': 'set-control', 'targets': ['amount'], 'value': 7, 'explanation': 'Change'},
            {'id': 'choose', 'operation': 'select', 'targets': ['values', 'item-0'], 'explanation': 'Select'},
            {'id': 'reset-all', 'operation': 'reset', 'targets': [], 'explanation': 'Reset'},
        ]}
        frames = compile_document(config)['frames']
        self.assertEqual(frames[0]['controls'], {'amount': 2})
        self.assertEqual(frames[2]['controls'], {'amount': 7})
        self.assertEqual(frames[2]['selection'], {'dataId': 'values', 'id': 'item-0'})
        self.assertEqual(frames[3]['controls'], {'amount': 2})
        self.assertIsNone(frames[3]['selection'])
        config['timeline']['steps'][0]['value'] = 11
        with self.assertRaises(ValueError):
            compile_document(config)

    def test_generator_cannot_replace_table_source_with_sequence(self):
        config = static_document({'dist': {'type': 'table', 'columns': [{'id': 'value', 'type': 'number'}], 'rows': []}}, 'table', 'dist')
        config['timeline'] = {'generator': 'bfs', 'input': {'n': 2, 'edges': [], 'source': 0}}
        with self.assertRaises(ValueError):
            compile_document(config)

    def test_authored_steps_cannot_break_numeric_bindings(self):
        config = static_document({'values': {'type': 'sequence', 'values': [1]}}, 'vector', 'values')
        config['bindings'] = [{'id': 'total', 'operation': 'sum', 'args': ['values'], 'target': 'view'}]
        config['timeline'] = {'steps': [{'id': 'append', 'operation': 'push', 'targets': ['values'], 'value': 'not a number', 'explanation': 'Append'}]}
        with self.assertRaises(ValueError):
            compile_document(config)



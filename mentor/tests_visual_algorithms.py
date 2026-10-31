import unittest

from .visual_algorithms import algorithm_document, compile_algorithm


class VisualAlgorithmTests(unittest.TestCase):
    def test_bfs_uses_fifo_sorted_neighbors_and_discovered_on_enqueue(self):
        inp = {'n': 4, 'edges': [[0, 2], [0, 1], [1, 3], [2, 3]], 'source': 0}
        document = algorithm_document('bfs', inp)
        frames = compile_algorithm('bfs', inp)
        self.assertEqual(frames[-1]['data']['dist']['values'], [0, 1, 1, 2])
        self.assertEqual(frames[-1]['data']['parent']['values'], [None, 0, 0, 1])
        discoveries = [frame['data']['dist']['values'] for frame in frames
                       if frame['title'] == 'Phát hiện láng giềng']
        self.assertEqual(discoveries[0][:3], [0, 1, None])
        self.assertEqual(discoveries[1][:3], [0, 1, 1])
        self.assertEqual(frames[-1]['data']['status']['values'], ['processed'] * 4)
        self.assertEqual(document['data']['graph']['nodes'][0]['id'], 'v0')
        self.assertEqual(set(frames[-1]['data']), set(document['data']))

    def test_dfs_tracks_real_recursive_frames_and_times(self):
        inp = {'n': 4, 'edges': [[0, 1], [0, 2], [1, 3]], 'source': 0}
        document = algorithm_document('dfs', inp)
        frames = compile_algorithm('dfs', inp)
        depth = [len(frame['data']['callstack']['scopes'][0]['frames']) for frame in frames]
        self.assertGreater(max(depth), 1)
        self.assertEqual(frames[-1]['data']['parent']['values'], [None, 0, 0, 1])
        self.assertEqual(frames[-1]['data']['discover']['values'], [1, 2, 6, 3])
        self.assertEqual(frames[-1]['data']['finish']['values'], [8, 5, 7, 4])
        self.assertEqual(frames[-1]['data']['status']['values'], ['finished', 'finished', 'finished', 'finished'])
        self.assertEqual(set(frames[-1]['data']), set(document['data']))

    def test_for_loop_matches_inclusive_sum_stdout_and_empty_range(self):
        frames = compile_algorithm('for-loop', {'start': 1, 'end': 5, 'step': 2})
        final = frames[-1]
        self.assertEqual(final['data']['variables']['scopes'][0]['frames'][0]['locals']['sum'], 9)
        self.assertEqual(frames[-2]['output'], '9\n')
        self.assertEqual(final['data']['iterations']['values'], [1, 3, 5])
        empty = compile_algorithm('for-loop', {'start': 5, 'end': 2, 'step': 1})
        self.assertEqual(empty[-1]['data']['iterations']['values'], [])
        self.assertEqual(empty[-2]['output'], '0\n')

    def test_matrix_chain_cost_and_split(self):
        frames = compile_algorithm('matrix-chain', {'dimensions': [10, 20, 5, 30]})
        self.assertEqual(frames[-1]['data']['cost']['values'][0][2], 2500)
        self.assertIsNotNone(frames[-1]['data']['split']['values'][0][2])

    def test_matching_is_independent_bitmask_count_with_valid_witness(self):
        matrix = [[1, 1, 0], [1, 0, 1], [0, 1, 1]]
        frames = compile_algorithm('dp-bitmask-matching', {'matrix': matrix})
        final = frames[-1]['data']
        self.assertEqual(final['dp']['values'][-1], 2)
        witness = final['witness']['rows']
        self.assertEqual(len(witness), 3)
        self.assertEqual(len({row['person'] for row in witness}), 3)
        self.assertEqual(len({row['job'] for row in witness}), 3)
        self.assertTrue(all(matrix[row['person']][row['job']] for row in witness))
        self.assertNotIn('output', frames[-1])


    def test_invalid_kind_or_document_id_is_rejected(self):
        with self.assertRaises(ValueError):
            algorithm_document('not-an-algorithm', {})
        with self.assertRaises(ValueError):
            algorithm_document('bfs', {'n': 1, 'edges': [], 'source': 0}, document_id='0bad')

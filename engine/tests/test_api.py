import unittest
from api.server import operation, agent
from engine.board import Board


class ApiTests(unittest.TestCase):
    def test_initial_move_and_search(self):
        state = operation({})
        self.assertEqual(tuple(state['legal']), (19, 26, 37, 44))
        moved = operation({'action': 'move', 'board': state['board'], 'move': 19})
        self.assertEqual(moved['turn'], -1)
        analysis = operation({'action': 'analyze', 'board': moved['board'], 'depth': 2})
        self.assertEqual(analysis['board'], moved['board'])
        self.assertIn(analysis['search']['move'], moved['legal'])
        next_state = operation({'action': 'step', 'board': moved['board'], 'depth': 2})
        self.assertEqual(next_state['board'], Board.deserialize(moved['board']).play(analysis['search']['move']).serialize())

    def test_invalid_requests(self):
        for payload in ({'action': 'move', 'move': 0}, {'action': 'unknown'}, {'action': 'step', 'depth': 0}, {'action': 'step', 'engine': 'unknown'}):
            with self.assertRaises(ValueError):
                operation(payload)

    def test_saved_evaluators_are_finite_and_bounded(self):
        try:
            import torch
        except ImportError:
            self.skipTest('Research dependencies not installed')
        b = Board.initial().play(19)
        for name in ('ga-ab', 'neural-ab'):
            evaluator = agent(name, 1).evaluator
            self.assertLessEqual(abs(evaluator(b, 1)), 1)
            self.assertAlmostEqual(evaluator(b, 1), -evaluator(b, -1))
            chosen = agent(name, 1).choose(b)
            self.assertIn(chosen.move, b.legal_moves())
            from engine.search import search
            mm = search(b, 2, evaluator, 'minimax')
            ab = search(b, 2, evaluator, 'alphabeta', 'position')
            self.assertEqual((mm.move, mm.value), (ab.move, ab.value))

import random
import unittest
from engine.board import Board
from engine.agents import RandomAgent
from engine.evaluation import Heuristic, features, terminal_value
from engine.search import search


class SearchTests(unittest.TestCase):
    def test_equivalence_positions_depths_orderings(self):
        positions, b, rng = [Board.initial()], Board.initial(), random.Random(32)
        for ply in range(55):
            if b.is_terminal():
                break
            moves = b.legal_moves()
            b = b.play(rng.choice(moves) if moves else None)
            if ply in (8, 20, 40, 52):
                positions.append(b)
        for b in positions:
            for depth in (0, 1, 2, 3):
                mm = search(b, depth, algorithm='minimax')
                for ordering in ('none', 'position', 'mobility'):
                    with self.subTest(board=b.serialize(), depth=depth, ordering=ordering):
                        ab = search(b, depth, algorithm='alphabeta', ordering=ordering)
                        self.assertEqual((mm.value, mm.move), (ab.value, ab.move))
                        self.assertLessEqual(ab.nodes, mm.nodes)

    def test_ties_independent_of_order(self):
        evaluator = lambda b, p: 0.0
        b = Board.initial().play(19)
        expected = min(b.legal_moves())
        for ordering in ('none', 'position', 'mobility'):
            self.assertEqual(search(b, 3, evaluator, ordering=ordering).move, expected)

    def test_pass_does_not_consume_placement_depth(self):
        cells = [1] * 64
        cells[0], cells[1] = 0, -1
        b = Board(tuple(cells), -1)
        for algorithm in ('minimax', 'alphabeta'):
            result = search(b, 1, algorithm=algorithm)
            self.assertIsNone(result.move)
            self.assertEqual(result.value, -3.0)
            self.assertEqual(result.max_depth, 1)

    def test_terminal_overrides_evaluator(self):
        b = Board((1,) * 64)
        r = search(b, 4, lambda b, p: -100)
        self.assertEqual(r.value, 3)
        self.assertEqual(r.nodes, 1)
        self.assertEqual(r.max_depth, 0)

    def test_depth_one_reference(self):
        b, evaluator = Board.initial().play(19), Heuristic()
        scores = {m: evaluator(b.play(m), b.turn) for m in b.legal_moves()}
        expected = min(scores, key=lambda m: (-scores[m], m))
        self.assertEqual(search(b, 1).move, expected)

    def test_features_antisymmetry_and_bounds(self):
        b = Board.initial().play(19)
        a, z = features(b, 1), features(b, -1)
        for name in a:
            self.assertAlmostEqual(a[name], -z[name])
            self.assertLessEqual(abs(a[name]), 1)
        self.assertAlmostEqual(Heuristic()(b, 1), -Heuristic()(b, -1))
        self.assertLessEqual(abs(Heuristic()(b, 1)), 1)

    def test_random_reproducible_and_legal(self):
        a, z, b = RandomAgent(99), RandomAgent(99), Board.initial()
        for _ in range(20):
            x, y = a.choose(b), z.choose(b)
            self.assertEqual(x.move, y.move)
            self.assertIn(x.move, b.legal_moves())
            b = b.play(x.move)

    def test_time_mode_matches_completed_depth(self):
        from engine.search import timed_search
        b = Board.initial()
        a, z = search(b, 2, ordering='position'), timed_search(b, 10, 2)
        self.assertEqual((a.move, a.value), (z.move, z.value))
        self.assertEqual(z.completed_depth, 2)
        self.assertGreaterEqual(z.nodes, a.nodes)
        short = timed_search(b, 0.000001, 20)
        self.assertIn(short.move, b.legal_moves())
        self.assertEqual(short.completed_depth, 0)

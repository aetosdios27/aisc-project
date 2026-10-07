import random
import unittest
from engine.board import Board, DIRECTIONS, coordinate, parse_move


class BoardTests(unittest.TestCase):
    def test_opening(self):
        b = Board.initial()
        self.assertEqual(b.counts(), {"black": 2, "white": 2, "empty": 60})
        self.assertEqual(b.legal_moves(), (19, 26, 37, 44))
        self.assertEqual(b.legal_moves(-1), (20, 29, 34, 43))
        self.assertFalse(b.is_terminal())

    def test_opening_move_and_immutability(self):
        b = Board.initial()
        next_board = b.play(19)
        self.assertEqual(next_board.counts(), {"black": 4, "white": 1, "empty": 59})
        self.assertEqual(next_board.cells[27], 1)
        self.assertEqual(next_board.turn, -1)
        self.assertEqual(b.cells[27], -1)

    def test_illegal(self):
        for move in (0, 27, -1, 64, None, True):
            with self.subTest(move=move), self.assertRaises(ValueError):
                Board.initial().play(move)

    def test_all_eight_directions(self):
        for dr, dc in DIRECTIONS:
            with self.subTest(direction=(dr, dc)):
                cells = [0] * 64
                adjacent = (3 + dr) * 8 + 3 + dc
                end = (3 + 2 * dr) * 8 + 3 + 2 * dc
                cells[adjacent], cells[end] = -1, 1
                b = Board(tuple(cells))
                self.assertEqual(b.captures(27), (adjacent,))
                self.assertEqual(b.play(27).cells[adjacent], 1)

    def test_multi_direction(self):
        cells = [0] * 64
        for dr, dc in DIRECTIONS:
            cells[(3 + dr) * 8 + 3 + dc] = -1
            cells[(3 + 2 * dr) * 8 + 3 + 2 * dc] = 1
        b = Board(tuple(cells))
        self.assertEqual(len(b.captures(27)), 8)
        self.assertEqual(b.play(27).counts()['black'], 17)

    def test_edges_corners_and_no_wrapping(self):
        cells = [0] * 64
        cells[1], cells[2], cells[8], cells[16], cells[9], cells[18] = -1, 1, -1, 1, -1, 1
        self.assertEqual(set(Board(tuple(cells)).captures(0)), {1, 8, 9})
        cells = [0] * 64
        cells[8], cells[9] = -1, 1
        self.assertEqual(Board(tuple(cells)).captures(7), ())

    def test_forced_pass(self):
        cells = [1] * 64
        cells[0], cells[1] = 0, -1
        b = Board(tuple(cells), -1)
        self.assertFalse(b.is_terminal())
        self.assertEqual(b.legal_moves(), ())
        p = b.play(None)
        self.assertEqual(p.passes, 1)
        self.assertEqual(p.legal_moves(), (0,))
        self.assertEqual(p.play(0).passes, 0)
        self.assertEqual(p.play(0).winner(), 1)

    def test_two_passes_and_nonfull_terminal(self):
        b = Board((1,) * 63 + (0,))
        self.assertTrue(b.is_terminal())
        p = b.play(None).play(None)
        self.assertEqual(p.passes, 2)
        self.assertTrue(p.is_terminal())
        with self.assertRaises(ValueError):
            p.play(None)

    def test_winners(self):
        for cells, winner in [((1,) * 64, 1), ((-1,) * 64, -1), ((1,) * 32 + (-1,) * 32, 0)]:
            self.assertTrue(Board(cells).is_terminal())
            self.assertEqual(Board(cells).winner(), winner)
        with self.assertRaises(ValueError):
            Board.initial().winner()

    def test_serialization_validation(self):
        b = Board.initial().play(19)
        self.assertEqual(Board.deserialize(b.serialize()), b)
        for value in ('bad', '.' * 64 + ':0:0', '.' * 64 + ':1:3'):
            with self.assertRaises(ValueError):
                Board.deserialize(value)
        for i in range(64):
            self.assertEqual(parse_move(coordinate(i)), i)

    def test_seeded_games_invariants(self):
        for seed in range(12):
            rng, b, turns = random.Random(seed), Board.initial(), 0
            while not b.is_terminal():
                moves = b.legal_moves()
                old_count, player = 64 - b.cells.count(0), b.turn
                move = rng.choice(moves) if moves else None
                flips = b.captures(move) if move is not None else ()
                next_board = b.play(move)
                self.assertEqual(64 - next_board.cells.count(0), old_count + (move is not None))
                self.assertEqual(next_board.turn, -player)
                for i in flips:
                    self.assertEqual(next_board.cells[i], player)
                b, turns = next_board, turns + 1
                self.assertLessEqual(turns, 120)
            self.assertIn(b.winner(), (-1, 0, 1))

    def test_long_ray_and_empty_gap(self):
        cells = [0] * 64
        cells[1:7], cells[7] = [-1] * 6, 1
        b = Board(tuple(cells))
        self.assertEqual(b.captures(0), tuple(range(1, 7)))
        self.assertEqual(b.play(0).cells[:8], (1,) * 8)
        cells[4] = 0
        self.assertEqual(Board(tuple(cells)).captures(0), ())

    def test_flips_do_not_chain(self):
        cells = [0] * 64
        cells[1], cells[2], cells[9], cells[17] = -1, 1, -1, 1
        b = Board(tuple(cells)).play(0)
        self.assertEqual(b.cells[1], 1)
        self.assertEqual(b.cells[9], -1)

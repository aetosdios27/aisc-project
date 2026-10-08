"""Independent reference rules and minimax, plus regressions for audit failures."""
import math
import random
import unittest
from engine.board import Board
from engine.search import search, timed_search
from api.server import operation


def reference_moves(cells, player):
    """Read each ray as a list; find a friendly endpoint after opponent prefix."""
    found = {}
    for square, value in enumerate(cells):
        if value:
            continue
        row, col = divmod(square, 8)
        captures = []
        for vertical in (-1, 0, 1):
            for horizontal in (-1, 0, 1):
                if vertical == horizontal == 0:
                    continue
                ray = [(row + step * vertical) * 8 + col + step * horizontal
                       for step in range(1, 8)
                       if 0 <= row + step * vertical < 8 and 0 <= col + step * horizontal < 8]
                endpoint = next((i for i, position in enumerate(ray) if cells[position] != -player), len(ray))
                if 0 < endpoint < len(ray) and cells[ray[endpoint]] == player:
                    captures.extend(ray[:endpoint])
        if captures:
            found[square] = tuple(captures)
    return found


def reference_child(cells, player, square, captures):
    return tuple(player if i == square or i in captures else x for i, x in enumerate(cells))


def reference_value(cells, turn, depth, root):
    moves = reference_moves(cells, turn)
    if not moves:
        if reference_moves(cells, -turn):
            return reference_value(cells, -turn, depth, root)
        difference = sum(cells)
        return 2 * ((difference > 0) - (difference < 0)) * root + difference * root / 64
    if depth == 0:
        return sum(cells) * root / 64
    children = [reference_value(reference_child(cells, turn, move, flips), -turn, depth - 1, root)
                for move, flips in moves.items()]
    return max(children) if turn == root else min(children)


class IndependentOracleTests(unittest.TestCase):
    def test_twenty_games_against_independent_rules(self):
        for seed in range(20):
            rng, board = random.Random(seed), Board.initial()
            while True:
                for player in (-1, 1):
                    expected = reference_moves(board.cells, player)
                    self.assertEqual(board.legal_moves(player), tuple(expected))
                    for move, captures in expected.items():
                        self.assertEqual(set(board.captures(move, player)), set(captures))
                if board.is_terminal():
                    self.assertFalse(reference_moves(board.cells, 1) or reference_moves(board.cells, -1))
                    break
                moves = reference_moves(board.cells, board.turn)
                if moves:
                    move = rng.choice(tuple(moves))
                    expected_cells = reference_child(board.cells, board.turn, move, moves[move])
                    board = board.play(move)
                    self.assertEqual(board.cells, expected_cells)
                else:
                    board = board.play(None)

    def test_search_against_independent_endgame_solver(self):
        for seed in range(5):
            rng, board = random.Random(910 + seed), Board.initial()
            while board.cells.count(0) > 5 and not board.is_terminal():
                moves = board.legal_moves()
                board = board.play(rng.choice(moves) if moves else None)
            depth = board.cells.count(0)
            value = reference_value(board.cells, board.turn, depth, board.turn)
            moves = reference_moves(board.cells, board.turn)
            expected_move = None
            if moves:
                scores = {m: reference_value(reference_child(board.cells, board.turn, m, f), -board.turn, depth - 1, board.turn)
                          for m, f in moves.items()}
                expected_move = min(scores, key=lambda m: (-scores[m], m))
            for algorithm in ('minimax', 'alphabeta'):
                for ordering in ('none', 'position', 'mobility'):
                    result = search(board, depth, lambda b, p: sum(b.cells) * p / 64, algorithm, ordering)
                    self.assertEqual((result.move, result.value), (expected_move, value))


class BoundaryRegressionTests(unittest.TestCase):
    def test_malformed_board_requests_are_validation_errors(self):
        for value in (None, True, 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                operation({'board': value})

    def test_invalid_player_rejected_on_full_board(self):
        for player in (True, 0, 2, 'black'):
            with self.subTest(player=player), self.assertRaises(ValueError):
                Board((1,) * 64).legal_moves(player)

    def test_bad_leaf_values_rejected(self):
        for value in (math.nan, math.inf, -math.inf, 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                search(Board.initial(), 1, lambda b, p: value)

    def test_bad_time_budgets_rejected(self):
        for seconds in (math.nan, math.inf, -math.inf, True, '1', 0):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                timed_search(Board.initial(), seconds, max_depth=1)

    def test_falsey_evaluator_is_respected(self):
        class Evaluator:
            def __bool__(self):
                return False
            def __call__(self, board, player):
                return 0.7
        self.assertEqual(search(Board.initial(), 1, Evaluator()).value, 0.7)

class MeasurementRegressionTests(unittest.TestCase):
    def test_pass_search_cost_is_in_total_but_not_placement_average(self):
        from experiments.tournament import summarize
        turns = [{'player': 1, 'move': None, 'nodes': 20, 'seconds': 0.5},
                 {'player': 1, 'move': 3, 'nodes': 4, 'seconds': 0.1}]
        summary = summarize([{'black': 'a', 'white': 'b', 'winner': 1, 'game_length': 60, 'turns': turns}], ['a'])['a']
        self.assertEqual(summary['total_nodes'], 24)
        self.assertEqual(summary['average_nodes'], 4)
        self.assertEqual(summary['passes'], 1)
        self.assertAlmostEqual(summary['total_search_seconds'], 0.6)

    def test_csv_preserves_color_performance(self):
        import csv
        import tempfile
        from pathlib import Path
        from experiments.tournament import tournament, save_results
        from engine.agents import RandomAgent
        result = tournament({'a': lambda s: RandomAgent(s), 'b': lambda s: RandomAgent(s + 1)}, 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            save_results(result, path)
            with path.with_suffix('.csv').open(newline='') as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['black_games'], '1')
        self.assertEqual(rows[0]['white_games'], '1')
        self.assertIn('white_score_rate', rows[0])

    def test_ga_reuses_generator_seeds_for_every_opponent(self):
        from unittest.mock import patch
        from evolution.ga import fitness
        from engine.evaluation import MANUAL_WEIGHTS
        fake_game = {'winner': 0, 'counts': {'black': 32, 'white': 32, 'empty': 0}}
        with patch('evolution.ga.simulate', return_value=fake_game) as games:
            value, records = fitness(MANUAL_WEIGHTS, [MANUAL_WEIGHTS] * 2, iter([9, 10]), 1)
        self.assertEqual(games.call_count, 8)
        self.assertEqual(len(records), 8)
        self.assertEqual(value, 0.5)

    def test_near_index_matches_brute_force_under_symmetries(self):
        from neural.dataset import NearIndex, symmetries
        rng = random.Random(141)
        rows = [tuple(rng.choice((-1, 0, 1)) for _ in range(64)) for _ in range(12)]
        index = NearIndex()
        for row in rows:
            index.add(row)
        for i in range(24):
            query = list(rng.choice(symmetries(rows[i % len(rows)])))
            for cell in rng.sample(range(64), i % 4):
                query[cell] = rng.choice([x for x in (-1, 0, 1) if x != query[cell]])
            expected = any(sum(a != b for a, b in zip(variant, row)) <= 2 for variant in symmetries(query) for row in rows)
            self.assertEqual(index.contains_near(tuple(query)), expected)

    def test_empty_preprocessing_preserves_existing_outputs(self):
        import tempfile
        from pathlib import Path
        from neural.dataset import preprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'empty.wtb'
            raw.write_bytes(bytes(16))
            output = root / 'processed'
            output.mkdir()
            previous = output / 'train.jsonl'
            previous.write_text('previous valid output\n')
            with self.assertRaises(ValueError):
                preprocess(raw, output)
            self.assertEqual(previous.read_text(), 'previous valid output\n')

    def test_custom_preprocessing_does_not_replace_default_manifest(self):
        import contextlib
        import io
        import struct
        import tempfile
        from pathlib import Path
        from neural.dataset import preprocess
        from experiments.tournament import digest
        report = Path('experiments/results/dataset_manifest.json')
        previous = digest(report)
        records = []
        for seed in range(32):
            rng, board, record = random.Random(seed), Board.initial(), bytearray(68)
            moves = []
            while not board.is_terminal():
                legal = board.legal_moves()
                move = rng.choice(legal) if legal else None
                board = board.play(move)
                if move is not None:
                    moves.append(10 * (move // 8 + 1) + move % 8 + 1)
            record[6] = 32 if board.winner() == 0 else board.cells.count(1) + (board.cells.count(0) if board.winner() == 1 else 0)
            record[8:8 + len(moves)] = bytes(moves)
            records.append(record)
        header = bytearray(16)
        struct.pack_into('<I', header, 4, len(records))
        header[12] = 8
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            raw = root / 'synthetic.wtb'
            raw.write_bytes(header + b''.join(records))
            result = preprocess(raw, root / 'processed')
            self.assertTrue(all(n > 0 for n in result['counts'].values()))
        self.assertEqual(digest(report), previous)

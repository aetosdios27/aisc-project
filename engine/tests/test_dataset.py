import struct
import unittest
from neural.dataset import parse_wthor, symmetries, NearIndex, encoding
from engine.board import Board


class DatasetTests(unittest.TestCase):
    def test_wthor_format(self):
        header, record = bytearray(16), bytearray(68)
        struct.pack_into('<I', header, 4, 1)
        header[12], record[6], record[8] = 8, 40, 56
        self.assertEqual(list(parse_wthor(header + record)), [(0, 40, [37])])
        with self.assertRaises(ValueError):
            list(parse_wthor(header + record[:-1]))
        record[10] = 12
        with self.assertRaises(ValueError):
            list(parse_wthor(header + record))

    def test_symmetry_and_near_index(self):
        values = tuple([0] * 20 + [1, -1] * 22)
        index = NearIndex()
        index.add(values)
        for variant in symmetries(values):
            self.assertTrue(index.contains_near(variant))
        near = list(values)
        near[0], near[1] = 1, -1
        self.assertTrue(index.contains_near(tuple(near)))
        far = tuple([1] * 64)
        self.assertFalse(index.contains_near(far))
        self.assertEqual(len(set(symmetries(tuple(range(64))))), 8)

    def test_relative_encoding(self):
        b = Board.initial()
        inverted = Board(tuple(-x for x in b.cells), -b.turn)
        self.assertEqual(encoding(b), encoding(inverted))

    def test_actual_splits_have_disjoint_games_and_symmetry_states(self):
        import json
        from pathlib import Path
        root = Path('data/processed')
        if not (root / 'manifest.json').exists():
            self.skipTest('Regenerate public dataset to run split integration audit')
        seen_games, seen_states = set(), set()
        for split in ('train', 'validation', 'test'):
            rows = [json.loads(line) for line in (root / f'{split}.jsonl').read_text().splitlines()]
            games = {row['game'] for row in rows}
            states = {min(symmetries(row['x'])) for row in rows}
            self.assertFalse(games & seen_games)
            self.assertFalse(states & seen_states)
            self.assertEqual(len(states), len(rows))
            seen_games.update(games)
            seen_states.update(states)

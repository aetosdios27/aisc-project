import random
import unittest
from engine.agents import RandomAgent
from engine.board import Board
from engine.evaluation import MANUAL_WEIGHTS
from evolution.ga import crossover, mutate, normalize, select
from experiments.tournament import tournament, simulate


class ExperimentTests(unittest.TestCase):
    def test_simulation_replay(self):
        game = simulate(RandomAgent(8), RandomAgent(9))
        b = Board.deserialize(game['initial'])
        for turn in game['turns']:
            b = b.play(turn['move'])
        self.assertEqual(b.serialize(), game['final'])
        self.assertEqual(b.winner(), game['winner'])

    def test_paired_colors_and_repeatability(self):
        def factory(name):
            def make(seed):
                agent = RandomAgent(seed)
                agent.name = name
                return agent
            return make
        first = tournament({'a': factory('a'), 'b': factory('b')}, 4)
        second = tournament({'a': factory('a'), 'b': factory('b')}, 4)
        self.assertEqual([g['final'] for g in first['games']], [g['final'] for g in second['games']])
        self.assertEqual(first['games'][0]['initial'], first['games'][1]['initial'])
        for row in first['summary'].values():
            self.assertEqual(row['colors']['black']['games'], 2)
            self.assertEqual(row['colors']['white']['games'], 2)
            self.assertEqual(row['wins'] + row['losses'] + row['draws'], 4)
        with self.assertRaises(ValueError):
            tournament({'a': factory('a'), 'b': factory('b')}, 3)

    def test_genetic_operators(self):
        a, b = normalize(MANUAL_WEIGHTS), normalize(tuple(reversed(MANUAL_WEIGHTS)))
        child = crossover(a, b, random.Random(2))
        for x, y, z in zip(a, b, child):
            self.assertLessEqual(min(x, y), z)
            self.assertGreaterEqual(max(x, y), z)
        self.assertEqual(mutate(a, random.Random(3)), mutate(a, random.Random(3)))
        self.assertAlmostEqual(sum(abs(w) for w in mutate(a, random.Random(3))), 1)
        self.assertIn(select([a, b], [0, 1], random.Random(1)), (a, b))

    def test_generation_replacement_preserves_elite(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from evolution.ga import evolve
        with tempfile.TemporaryDirectory() as directory, patch('evolution.ga.fitness', side_effect=lambda weights, *args: (weights[0], [])), contextlib.redirect_stdout(io.StringIO()):
            result = evolve(3, 2, 1, 1, 333, str(Path(directory) / 'ga.json'))
        self.assertEqual(result['history'][1]['population'][0], result['history'][0]['weights'])

    def test_paired_bootstrap_uses_color_blocks(self):
        from experiments.analyze import paired_intervals
        games = []
        for seed in range(3):
            for black, white in (('a', 'b'), ('b', 'a')):
                games.append({'black': black, 'white': white, 'opening_seed': seed, 'initial': str(seed), 'winner': 1})
        row = paired_intervals(games, 100)[0]
        self.assertEqual(row['first_score_rate'], 0.5)
        self.assertEqual(row['first_score_interval95'], [0.5, 0.5])
        self.assertEqual(row['opening_pairs'], 3)

    def test_factory_labels_identify_same_agent_class(self):
        result = tournament({'first': lambda seed: RandomAgent(seed), 'second': lambda seed: RandomAgent(seed + 1)}, 2)
        self.assertEqual(result['summary']['first']['games'], 2)
        self.assertEqual(result['summary']['second']['games'], 2)
        self.assertEqual(result['games'][0]['black'], 'first')
        self.assertEqual(result['games'][0]['game_length'], 60 - Board.deserialize(result['games'][0]['final']).cells.count(0))

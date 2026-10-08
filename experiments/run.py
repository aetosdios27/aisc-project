"""Actual measurements only; small defaults are a pilot, not a research conclusion."""
import argparse
import csv
import json
from pathlib import Path
from engine.agents import RandomAgent, GreedyAgent, SearchAgent
from engine.evaluation import Heuristic
from engine.search import search, timed_search
from experiments.tournament import opening, tournament, save_results, provenance, digest


def factories(depth=2, time_budget=None):
    from neural.model import NeuralEvaluator
    ga = Heuristic(tuple(json.loads(Path('experiments/results/ga.json').read_text())['weights']))
    neural = NeuralEvaluator()
    return {
        'random': lambda seed: RandomAgent(seed),
        'manual-greedy': lambda seed: GreedyAgent(),
        'manual-minimax': lambda seed: SearchAgent('manual-minimax', depth, algorithm='minimax', ordering='position', time_budget=time_budget),
        'manual-ab': lambda seed: SearchAgent('manual-ab', depth, time_budget=time_budget),
        'ga-ab': lambda seed: SearchAgent('ga-ab', depth, ga, time_budget=time_budget),
        'neural-ab': lambda seed: SearchAgent('neural-ab', depth, neural, time_budget=time_budget),
    }


def benchmark(depths=(1, 2, 3), positions=6, seed=931):
    depths = tuple(depths)
    if not depths or any(type(d) is not int or d < 1 for d in depths):
        raise ValueError('Benchmark depths must be positive integers')
    if type(positions) is not int or not 1 <= positions <= 10:
        raise ValueError('Use 1–10 benchmark positions with nonterminal seeded openings')
    rows, time_rows = [], []
    for index in range(positions):
        board, _ = opening(seed + index, 12 + index * 5)
        for depth in depths:
            mm = search(board, depth, algorithm='minimax')
            for ordering in ('none', 'position', 'mobility'):
                ab = search(board, depth, ordering=ordering)
                if (mm.move, mm.value) != (ab.move, ab.value):
                    raise AssertionError('Search equivalence failed in benchmark')
                rows.append({'position': index, 'board': board.serialize(), 'depth': depth, 'ordering': ordering,
                             'move': mm.move, 'value': mm.value, 'minimax_nodes': mm.nodes, 'alphabeta_nodes': ab.nodes,
                             'nodes_saved': mm.nodes - ab.nodes, 'pruning_percentage': 100 * (mm.nodes - ab.nodes) / mm.nodes,
                             'cutoffs': ab.cutoffs, 'skipped_children': ab.skipped_children,
                             'minimax_seconds': mm.seconds, 'alphabeta_seconds': ab.seconds})
            if index == 0:
                fixed = search(board, depth, ordering='position')
                timed = timed_search(board, 60, depth)
                if (fixed.move, fixed.value) != (timed.move, timed.value):
                    raise AssertionError('Iterative search changed the completed-depth result')
                time_rows.append({'depth': depth, 'fixed_nodes': fixed.nodes, 'iterative_nodes': timed.nodes,
                                  'fixed_seconds': fixed.seconds, 'iterative_seconds': timed.seconds})
        print(f'Benchmark position {index + 1}/{positions} complete', flush=True)
    result = {'config': {'depths': list(depths), 'positions': positions, 'seed': seed},
              'provenance': provenance(), 'rows': rows, 'time_mode_overhead': time_rows}
    Path('experiments/results/benchmark.json').write_text(json.dumps(result, indent=2))
    with Path('experiments/results/benchmark.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return result


def run(games=20, depth=2, seed=1200, time_budget=None, depth_games=8):
    result = tournament(factories(depth, time_budget), games, seed)
    result['config'].update(depth=depth, time_budget=time_budget, status='pilot',
                            ga_sha256=digest('experiments/results/ga.json'), checkpoint_sha256=digest('neural/checkpoint.pt'))
    save_results(result, 'experiments/results/tournament.json')
    print('Main round robin complete', flush=True)
    depth_results = []
    for d in (1, 2, 3):
        def reference(seed):
            return SearchAgent('reference-d1', 1)
        def candidate(seed):
            return SearchAgent(f'manual-d{d}', d)
        study = tournament({'reference-d1': reference, f'manual-d{d}': candidate}, depth_games, seed + 1000)
        study['config'].update(candidate_depth=d, reference_depth=1)
        depth_results.append(study)
        print(f'Depth {d} strength study complete', flush=True)
    Path('experiments/results/depth.json').write_text(json.dumps({'studies': depth_results, 'status': 'pilot'}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', type=int, default=20)
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--seed', type=int, default=1200)
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--benchmark-only', action='store_true')
    args = parser.parse_args()
    benchmark()
    if not args.benchmark_only:
        run(args.games, args.depth, args.seed, args.seconds)

"""Tournament selection, arithmetic crossover, Gaussian mutation, elitism."""
import argparse
import csv
import json
import random
from math import isfinite
from pathlib import Path
from statistics import mean, pstdev
from engine.agents import SearchAgent
from engine.evaluation import Heuristic, MANUAL_WEIGHTS, FEATURES
from experiments.tournament import opening, simulate, provenance


def normalize(weights):
    if len(weights) != len(FEATURES) or not all(type(w) in (int, float) and isfinite(w) for w in weights):
        raise ValueError('Seven finite weights required')
    scale = sum(abs(w) for w in weights)
    if not isfinite(scale):
        raise ValueError('Weight norm must be finite')
    return tuple(w / scale for w in weights) if scale else MANUAL_WEIGHTS


def select(population, fitness, rng, size=3):
    candidates = [rng.randrange(len(population)) for _ in range(size)]
    return population[max(candidates, key=lambda i: (fitness[i], -i))]


def crossover(a, b, rng):
    t = rng.random()
    return tuple(t * x + (1 - t) * y for x, y in zip(a, b))


def mutate(weights, rng, rate=0.3, sigma=0.1):
    return normalize(tuple(w + rng.gauss(0, sigma) if rng.random() < rate else w for w in weights))


def fitness(weights, opponents, seeds, depth):
    opponents, seeds = tuple(opponents), tuple(seeds)
    if not opponents or not seeds or not all(type(seed) is int for seed in seeds):
        raise ValueError('A nonempty opponent panel and integer opening seeds are required')
    points, records = 0.0, []
    candidate = Heuristic(tuple(weights))
    for opponent in opponents:
        for seed in seeds:
            board, _ = opening(seed)
            for color in (1, -1):
                a = SearchAgent('candidate', depth, candidate)
                b = SearchAgent('opponent', depth, Heuristic(tuple(opponent)))
                game = simulate(a, b, board) if color == 1 else simulate(b, a, board)
                points += 1 if game['winner'] == color else 0.5 if game['winner'] == 0 else 0
                records.append({'seed': seed, 'color': color, 'winner': game['winner'], 'counts': game['counts']})
    return points / len(records), records


def evolve(population_size=6, generations=4, pairs=2, depth=1, seed=440, output='experiments/results/ga.json'):
    if not all(type(x) is int for x in (population_size, generations, pairs, depth, seed)) or population_size < 3 or generations < 1 or pairs < 1 or depth < 1:
        raise ValueError('Population >= 3, generations/pairs/depth >= 1 required')
    rng = random.Random(seed)
    population = [normalize(MANUAL_WEIGHTS)] + [mutate(MANUAL_WEIGHTS, rng, 1, 0.2) for _ in range(population_size - 1)]
    history, champion, validation = [], normalize(MANUAL_WEIGHTS), -1.0
    best = champion
    for generation in range(generations):
        # Same panel and openings for all candidates. Freeze before selection.
        panel = [normalize(MANUAL_WEIGHTS), champion, rng.choice(population)]
        evaluations = [fitness(w, panel, range(seed, seed + pairs), depth) for w in population]
        scores = [score for score, _ in evaluations]
        index = max(range(population_size), key=lambda i: (scores[i], -i))
        champion = population[index]
        # Comparable fixed validation panel; separate seeds from fitness and final tests.
        validation_start = seed + max(1000, pairs)
        validation_score, heldout = fitness(champion, [normalize(MANUAL_WEIGHTS)], range(validation_start, validation_start + pairs), depth)
        if validation_score > validation:
            best, validation = champion, validation_score
        history.append({'generation': generation, 'best_fitness': scores[index], 'average_fitness': mean(scores),
                        'diversity': mean(pstdev(w[j] for w in population) for j in range(len(FEATURES))),
                        'weights': champion, 'validation_score': validation_score,
                        'population': population, 'fitness': scores, 'opponents': panel,
                        'tournament_results': [records for _, records in evaluations], 'validation_results': heldout})
        print(f'GA generation {generation}: fitness={scores[index]:.3f}, validation={validation_score:.3f}', flush=True)
        next_population = [champion]  # exact elitism
        while len(next_population) < population_size:
            next_population.append(mutate(crossover(select(population, scores, rng), select(population, scores, rng), rng), rng))
        population = next_population
    result = {'config': {'population': population_size, 'generations': generations, 'pairs': pairs, 'depth': depth, 'seed': seed},
              'provenance': provenance(), 'features': FEATURES, 'weights': best,
              'validation_score': validation, 'history': history}
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    with path.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('generation', 'best_fitness', 'average_fitness', 'diversity', 'validation_score'))
        writer.writeheader()
        writer.writerows({k: row[k] for k in writer.fieldnames} for row in history)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--population', type=int, default=6)
    parser.add_argument('--generations', type=int, default=4)
    parser.add_argument('--pairs', type=int, default=2)
    parser.add_argument('--depth', type=int, default=1)
    parser.add_argument('--seed', type=int, default=440)
    args = parser.parse_args()
    evolve(args.population, args.generations, args.pairs, args.depth, args.seed)

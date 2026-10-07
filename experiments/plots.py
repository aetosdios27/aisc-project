import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('experiments/results')
OUTPUT = Path('experiments/plots')


def save(name, title, xlabel, ylabel):
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(axis='y', alpha=0.2)
    plt.tight_layout()
    plt.savefig(OUTPUT / f'{name}.png', dpi=160)
    plt.close()


def generate():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tournament = json.loads((ROOT / 'tournament.json').read_text())
    names = list(tournament['summary'])
    plt.figure(figsize=(10, 4))
    plt.bar(names, [tournament['summary'][n]['score_rate'] for n in names], color='#278878')
    plt.ylim(0, 1)
    plt.xticks(rotation=15)
    save('round_robin', 'Pilot: pooled round-robin score rate (draw = ½)', 'Engine', 'Score rate')
    for name, first, second in (('manual_ga', 'manual-ab', 'ga-ab'), ('manual_neural', 'manual-ab', 'neural-ab'), ('ga_neural', 'ga-ab', 'neural-ab')):
        group = [g for g in tournament['games'] if {g['black'], g['white']} == {first, second}]
        rates = []
        for engine in (first, second):
            rates.append(sum(0.5 if g['winner'] == 0 else int(g['winner'] == (1 if g['black'] == engine else -1)) for g in group) / len(group))
        plt.figure(figsize=(6, 4))
        plt.bar((first, second), rates, color=('#278878', '#c58738'))
        plt.ylim(0, 1)
        save(name, f'Pilot: {len(group)} paired games at equal depth', 'Evaluator + Alpha-Beta', 'Score rate')
    rows = json.loads((ROOT / 'benchmark.json').read_text())['rows']
    depths = sorted({r['depth'] for r in rows})
    for name, field, ylabel in (('nodes', 'nodes', 'Mean visited nodes'), ('runtime', 'seconds', 'Mean seconds / search')):
        plt.figure(figsize=(7, 4))
        for algorithm in ('minimax', 'alphabeta'):
            selected = [r for r in rows if r['ordering'] == 'position']
            averages = [sum(r[f'{algorithm}_{field}'] for r in selected if r['depth'] == d) / sum(r['depth'] == d for r in selected) for d in depths]
            plt.plot(depths, averages, 'o-', label=algorithm)
        plt.legend()
        save(name, 'Search on identical seeded positions', 'Placement depth', ylabel)
    history = json.loads((ROOT / 'ga.json').read_text())['history']
    plt.figure(figsize=(7, 4))
    for field in ('best_fitness', 'average_fitness', 'validation_score'):
        plt.plot([r['generation'] for r in history], [r[field] for r in history], 'o-', label=field)
    plt.legend()
    save('ga', 'GA pilot (training opponent panel changes)', 'Generation', 'Game score rate')
    history = json.loads((ROOT / 'neural.json').read_text())['history']
    plt.figure(figsize=(7, 4))
    for field in ('training_loss', 'validation_loss'):
        plt.plot([r['epoch'] for r in history], [r[field] for r in history], label=field)
    plt.legend()
    save('neural', 'Neural outcome regression', 'Epoch', 'Mean squared error')
    studies = json.loads((ROOT / 'depth.json').read_text())['studies']
    plt.figure(figsize=(7, 4))
    plt.plot([s['config']['candidate_depth'] for s in studies],
             [s['summary'][f"manual-d{s['config']['candidate_depth']}"]['score_rate'] for s in studies], 'o-')
    plt.ylim(0, 1)
    save('depth_strength', 'Pilot: manual evaluator vs fixed depth-one reference', 'Candidate depth', 'Score rate')
    print('Generated nine charts from saved experiment outputs')


if __name__ == '__main__':
    generate()

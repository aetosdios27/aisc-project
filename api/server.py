"""Thin local HTTP adapter. Every game rule remains in engine.board."""
import argparse
import json
from dataclasses import asdict
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from engine.board import Board
from engine.agents import RandomAgent, SearchAgent, GreedyAgent
from engine.evaluation import Heuristic
from experiments.tournament import digest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('random', 'manual-greedy', 'manual-minimax', 'manual-ab', 'ga-ab', 'neural-ab')


@lru_cache(maxsize=1)
def neural_evaluator():
    from neural.model import NeuralEvaluator
    return NeuralEvaluator(ROOT / 'neural/checkpoint.pt')


def agent(name, depth=2, seed=0, time_budget=None):
    if name not in ENGINES:
        raise ValueError('Unknown engine')
    if type(depth) is not int or not 1 <= depth <= 5:
        raise ValueError('Demo depth must be an integer from 1 to 5')
    if type(seed) is not int:
        raise ValueError('Seed must be an integer')
    if time_budget is not None and (type(time_budget) not in (int, float) or not 0.001 <= time_budget <= 2):
        raise ValueError('Demo time budget must be between 0.001 and 2 seconds')
    if name == 'random':
        return RandomAgent(seed)
    if name == 'manual-greedy':
        return GreedyAgent()
    evaluator = Heuristic()
    if name == 'ga-ab':
        evaluator = Heuristic(tuple(json.loads((ROOT / 'experiments/results/ga.json').read_text())['weights']))
    if name == 'neural-ab':
        evaluator = neural_evaluator()
    return SearchAgent(name, depth, evaluator, 'minimax' if name == 'manual-minimax' else 'alphabeta',
                       time_budget=time_budget)


def describe(board):
    terminal = board.is_terminal()
    return {'board': board.serialize(), 'cells': board.cells, 'turn': board.turn,
            'legal': board.legal_moves(), 'terminal': terminal,
            'winner': board.winner() if terminal else None, 'counts': board.counts(),
            'manual_evaluation': Heuristic()(board, board.turn),
            'features': Heuristic().explain(board, board.turn)}


def operation(payload):
    if not isinstance(payload, dict):
        raise ValueError('Expected a JSON object')
    action = payload.get('action', 'state')
    board = Board.deserialize(payload['board']) if 'board' in payload else Board.initial()
    if action == 'move':
        if 'move' not in payload:
            raise ValueError('Move is required; use null for an explicit pass')
        board = board.play(payload['move'])
        return describe(board)
    if action in ('analyze', 'step'):
        selected = agent(payload.get('engine', 'manual-ab'), payload.get('depth', 2),
                         payload.get('seed', 0), payload.get('seconds'))
        if board.is_terminal():
            return describe(board)
        result = selected.choose(board)
        before = board.serialize()
        if action == 'step':
            board = board.play(result.move)
        response = describe(board)
        response['search'] = {'engine': selected.name, 'position': before, **asdict(result)}
        return response
    if action != 'state':
        raise ValueError('Unknown action')
    return describe(board)


def saved_results(root=ROOT):
    """Read a self-contained snapshot; expose hashes so stale evidence is visible."""
    result = {}
    for name in ('tournament', 'benchmark', 'ga', 'neural', 'depth', 'analysis'):
        target = root / 'experiments/results' / f'{name}.json'
        if not target.exists():
            continue
        data = json.loads(target.read_text())
        data['artifact_sha256'] = digest(target)
        games = data.pop('games', None)
        if name == 'tournament':
            pairs = {}
            for game in games:
                key = ' / '.join(sorted((game['black'], game['white'])))
                row = pairs.setdefault(key, {'games': 0, 'engines': {n: 0 for n in (game['black'], game['white'])}})
                row['games'] += 1
                for engine in row['engines']:
                    row['engines'][engine] += 0.5 if game['winner'] == 0 else int(game['winner'] == (1 if game['black'] == engine else -1))
            data['pairs'] = pairs
        if name == 'ga':
            for row in data['history']:
                for field in ('population', 'tournament_results', 'validation_results'):
                    row.pop(field, None)
        if name == 'depth':
            for study in data['studies']:
                study.pop('games', None)
        result[name] = data
    manifest = root / 'experiments/plots/manifest.json'
    if manifest.exists():
        plots = json.loads(manifest.read_text())
        plots['sources_match'] = all(name in result and result[name]['artifact_sha256'] == expected
                                     for name, expected in plots['sources'].items())
        result['plots'] = plots
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def json_response(self, data, status=200):
        encoded = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/state':
            self.json_response(describe(Board.initial()))
        elif path == '/api/results':
            try:
                self.json_response(saved_results())
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.json_response({'error': f'Saved experiment artifacts are incomplete or invalid: {exc}'}, 503)
        elif path.startswith('/plots/'):
            filename = path.removeprefix('/plots/')
            if '/' in filename or not filename.endswith('.png'):
                self.send_error(404)
                return
            target = ROOT / 'experiments/plots' / filename
            if not target.is_file():
                self.send_error(404)
                return
            content = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != '/api/game':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 16384:
                raise ValueError('Expected a small JSON game request')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object')
            self.json_response(operation(payload))
        except (ValueError, TypeError, KeyError) as exc:
            self.json_response({'error': str(exc)}, 400)
        except (ImportError, FileNotFoundError) as exc:
            self.json_response({'error': f'Required artifact or dependency missing: {exc}'}, 503)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    print(f'othello-ai local laboratory: http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()

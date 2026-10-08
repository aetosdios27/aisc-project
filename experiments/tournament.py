"""Paired games with common random openings and swapped colors."""
import csv
import hashlib
import json
import platform
import random
from dataclasses import asdict
from pathlib import Path
from engine.board import Board


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance():
    paths = sorted(p for directory in ('engine', 'evolution', 'neural', 'experiments')
                   for p in Path(directory).glob('*.py'))
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'source_sha256': {str(p): digest(p) for p in paths}}


def opening(seed, plies=8):
    rng, board = random.Random(seed), Board.initial()
    moves = []
    for _ in range(plies):
        if board.is_terminal():
            break
        legal = board.legal_moves()
        move = rng.choice(legal) if legal else None
        moves.append(move)
        board = board.play(move)
    return board, moves


def simulate(black, white, board=None):
    board = board or Board.initial()
    initial = board.serialize()
    agents, turns = {1: black, -1: white}, []
    while not board.is_terminal():
        player = board.turn
        result = agents[player].choose(board)
        if result.move is None and board.legal_moves():
            raise ValueError('Agent passed illegally')
        board = board.play(result.move)
        turns.append({'player': player, **asdict(result)})
        if len(turns) > 120:
            raise RuntimeError('Game exceeded theoretical turn bound')
    return {'black': black.name, 'white': white.name, 'initial': initial,
            'final': board.serialize(), 'winner': board.winner(), 'counts': board.counts(),
            'game_length': sum(t['move'] is not None for t in turns), 'turns': turns}


def summarize(games, names):
    result = {}
    for name in names:
        selected = [g for g in games if name in (g['black'], g['white'])]
        wins = losses = draws = 0
        colors = {}
        turns = []
        for color, player in (('black', 1), ('white', -1)):
            group = [g for g in selected if g[color] == name]
            w = sum(g['winner'] == player for g in group)
            d = sum(g['winner'] == 0 for g in group)
            colors[color] = {'games': len(group), 'wins': w, 'draws': d, 'losses': len(group) - w - d,
                             'score_rate': (w + 0.5 * d) / len(group) if group else 0}
            wins, draws, losses = wins + w, draws + d, losses + len(group) - w - d
            turns.extend(t for g in group for t in g['turns'] if t['player'] == player)
        placements = [t for t in turns if t['move'] is not None]
        n, total_nodes = len(selected), sum(t['nodes'] for t in turns)
        result[name] = {'games': n, 'wins': wins, 'losses': losses, 'draws': draws,
                        'win_rate': wins / n if n else 0, 'score_rate': (wins + 0.5 * draws) / n if n else 0,
                        'average_game_length': sum(g['game_length'] for g in selected) / n if n else 0,
                        'average_search_seconds': sum(t['seconds'] for t in placements) / len(placements) if placements else 0,
                        'average_nodes': sum(t['nodes'] for t in placements) / len(placements) if placements else 0,
                        'total_nodes': total_nodes, 'total_search_seconds': sum(t['seconds'] for t in turns),
                        'placements': len(placements), 'passes': len(turns) - len(placements), 'colors': colors}
    return result


def tournament(factories, games_per_pair=12, seed=2026, opening_plies=8):
    if type(games_per_pair) is not int or games_per_pair < 2 or games_per_pair % 2:
        raise ValueError('Use a positive even game count for paired colors')
    if len(factories) < 2 or not all(isinstance(name, str) and name for name in factories):
        raise ValueError('At least two named agents are required')
    if type(seed) is not int or type(opening_plies) is not int or not 0 <= opening_plies <= 60:
        raise ValueError('Use an integer seed and opening length from 0 to 60')
    names, games = list(factories), []
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            for pair in range(games_per_pair // 2):
                board, moves = opening(seed + pair, opening_plies)
                for black, white in ((first, second), (second, first)):
                    game = simulate(factories[black](seed + pair), factories[white](seed + pair), board)
                    # Factory keys identify tournament entries even when agent classes share names.
                    game['black'], game['white'] = black, white
                    game['continuation_length'] = game['game_length']
                    game['game_length'] += sum(move is not None for move in moves)
                    game.update(pair=pair, opening_seed=seed + pair, opening_moves=moves)
                    games.append(game)
    return {'config': {'games_per_pair': games_per_pair, 'seed': seed, 'opening_plies': opening_plies},
            'provenance': provenance(), 'summary': summarize(games, names), 'games': games}


def save_results(result, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    summary = [{k: v for k, v in row.items() if k != 'colors'} | {'engine': name} |
               {f'{color}_{key}': value for color, values in row['colors'].items() for key, value in values.items()}
               for name, row in result['summary'].items()]
    if not summary:
        raise ValueError('No engine summaries to save')
    with path.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

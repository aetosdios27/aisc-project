"""Explicit MAX/MIN recurrences. No game/search library is used."""
from dataclasses import dataclass
from math import inf
from time import perf_counter
from engine.evaluation import Heuristic, POSITION, CORNERS, terminal_value


@dataclass
class SearchResult:
    move: int | None
    value: float
    nodes: int = 0
    leaves: int = 0
    cutoffs: int = 0
    skipped_children: int = 0
    max_depth: int = 0
    seconds: float = 0.0
    completed_depth: int = 0


def ordered_moves(board, ordering):
    moves = board.legal_moves()
    if ordering == 'none':
        return moves
    if ordering == 'position':
        return tuple(sorted(moves, key=lambda m: (m not in CORNERS, -POSITION[m], m)))
    if ordering == 'mobility':
        return tuple(sorted(moves, key=lambda m: (m not in CORNERS, -POSITION[m], len(board.play(m).legal_moves()), m)))
    raise ValueError('Ordering must be none, position, or mobility')


class SearchTimeout(Exception):
    def __init__(self, stats):
        self.stats = stats


def search(board, depth=3, evaluator=None, algorithm='alphabeta', ordering='none', _deadline=None):
    if type(depth) is not int or depth < 0:
        raise ValueError('Depth must be a nonnegative integer')
    if algorithm not in ('minimax', 'alphabeta'):
        raise ValueError('Unknown search algorithm')
    evaluator = evaluator or Heuristic()
    ordered_moves(board, ordering)  # validate even for terminal positions
    start, perspective = perf_counter(), board.turn
    stats = SearchResult(None, 0.0, completed_depth=depth)

    def visit(state, remaining, alpha, beta, ply):
        if _deadline is not None and perf_counter() >= _deadline:
            raise SearchTimeout(stats)
        stats.nodes += 1
        stats.max_depth = max(stats.max_depth, ply)
        if state.is_terminal():
            stats.leaves += 1
            return terminal_value(state, perspective)
        moves = ordered_moves(state, ordering)
        if not moves:
            return visit(state.play(None), remaining, alpha, beta, ply)
        if remaining == 0:
            stats.leaves += 1
            return float(evaluator(state, perspective))
        maximizing = state.turn == perspective
        best = -inf if maximizing else inf
        for index, move in enumerate(moves):
            value = visit(state.play(move), remaining - 1, alpha, beta, ply + 1)
            best = max(best, value) if maximizing else min(best, value)
            if algorithm == 'alphabeta':
                if maximizing:
                    alpha = max(alpha, best)
                else:
                    beta = min(beta, best)
                if alpha >= beta and index + 1 < len(moves):
                    stats.cutoffs += 1
                    # Count skipped immediate children; descendants are unknown.
                    stats.skipped_children += len(moves) - index - 1
                    break
        return best

    if depth == 0 or board.is_terminal() or not board.legal_moves():
        stats.value = visit(board, depth, -inf, inf, 0)
    else:
        stats.nodes, stats.value = 1, -inf
        # Full root windows make each candidate value exact. Lower index wins ties
        # independently of ordering. Sacrifices some root pruning for explainability.
        for move in ordered_moves(board, ordering):
            value = visit(board.play(move), depth - 1, -inf, inf, 1)
            if value > stats.value or (value == stats.value and (stats.move is None or move < stats.move)):
                stats.move, stats.value = move, value
    stats.seconds = perf_counter() - start
    return stats


def minimax(board, depth=3, evaluator=None):
    return search(board, depth, evaluator, 'minimax')


def alphabeta(board, depth=3, evaluator=None, ordering='none'):
    return search(board, depth, evaluator, 'alphabeta', ordering)


def timed_search(board, seconds, max_depth=64, evaluator=None, ordering='position', algorithm='alphabeta'):
    """Return only a fully completed iteration; wall time is best effort on CPU."""
    if seconds <= 0 or max_depth < 1:
        raise ValueError('Positive time budget and maximum depth required')
    evaluator = evaluator or Heuristic()
    start = perf_counter()
    deadline = start + seconds
    moves = board.legal_moves()
    best = SearchResult(min(moves) if moves else None,
                        terminal_value(board, board.turn) if board.is_terminal() else float(evaluator(board, board.turn)))
    totals = {'nodes': 0, 'leaves': 0, 'cutoffs': 0, 'skipped_children': 0}
    maximum = 0
    for depth in range(1, max_depth + 1):
        try:
            iteration = search(board, depth, evaluator, algorithm, ordering, _deadline=deadline)
        except SearchTimeout as exc:
            iteration = exc.stats
            for key in totals:
                totals[key] += getattr(iteration, key)
            maximum = max(maximum, iteration.max_depth)
            break
        best = iteration
        for key in totals:
            totals[key] += getattr(iteration, key)
        maximum = max(maximum, iteration.max_depth)
        if board.is_terminal() or depth >= board.cells.count(0):
            break
    for key, value in totals.items():
        setattr(best, key, value)
    best.max_depth = maximum
    best.seconds = perf_counter() - start
    return best

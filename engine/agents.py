import random
from time import perf_counter
from math import isfinite
from engine.evaluation import Heuristic
from engine.search import SearchResult, search, timed_search, validate_options


class RandomAgent:
    name = 'random'

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def choose(self, board):
        start = perf_counter()
        moves = board.legal_moves()
        return SearchResult(self.rng.choice(moves) if moves else None, 0.0, seconds=perf_counter() - start)


class SearchAgent:
    def __init__(self, name='manual-ab', depth=3, evaluator=None, algorithm='alphabeta', ordering='position', time_budget=None):
        validate_options(depth, algorithm, ordering)
        if depth < 1:
            raise ValueError('Playing agents need depth >= 1')
        if time_budget is not None and (type(time_budget) not in (int, float) or not isfinite(time_budget) or time_budget <= 0):
            raise ValueError('Time budget must be finite and positive')
        self.name, self.depth = name, depth
        self.evaluator = Heuristic() if evaluator is None else evaluator
        self.algorithm, self.ordering = algorithm, ordering
        self.time_budget = time_budget

    def choose(self, board):
        if self.time_budget is not None:
            return timed_search(board, self.time_budget, self.depth, self.evaluator, self.ordering, self.algorithm)
        return search(board, self.depth, self.evaluator, self.algorithm, self.ordering)


class GreedyAgent:
    name = 'manual-greedy'

    def __init__(self, evaluator=None):
        self.evaluator = Heuristic() if evaluator is None else evaluator

    def choose(self, board):
        # A one-placement greedy evaluator is depth-one Minimax.
        return search(board, 1, self.evaluator, 'minimax', 'none')

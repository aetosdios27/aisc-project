"""All features are oriented toward a specified player and bounded by [-1, 1]."""
from dataclasses import dataclass
from math import isfinite
from engine.board import Board, DIRECTIONS

FEATURES = ('piece', 'mobility', 'corner', 'frontier', 'position', 'potential', 'danger')
CORNERS = (0, 7, 56, 63)
# Interpretable square categories: corner=4, corner-adjacent=-3,
# remaining edge=2, interior=1. This is a hypothesis, not fitted evidence.
def square_weight(i):
    r, c = divmod(i, 8)
    if i in CORNERS:
        return 4
    if any(max(abs(r - cr), abs(c - cc)) == 1 for cr, cc in ((0, 0), (0, 7), (7, 0), (7, 7))):
        return -3
    return 2 if r in (0, 7) or c in (0, 7) else 1

POSITION = tuple(square_weight(i) for i in range(64))
POSITION_SCALE = sum(abs(x) for x in POSITION)
MANUAL_WEIGHTS = (0.05, 0.25, 0.30, 0.10, 0.10, 0.10, 0.10)


def ratio(a, b):
    return (a - b) / (a + b) if a + b else 0.0


def features(board: Board, player: int) -> dict[str, float]:
    if player not in (-1, 1):
        raise ValueError('Invalid player')
    cells = board.cells
    adjacent = []
    for i in range(64):
        r, c = divmod(i, 8)
        adjacent.append(tuple((r + dr) * 8 + c + dc for dr, dc in DIRECTIONS
                              if 0 <= r + dr < 8 and 0 <= c + dc < 8))
    def frontier(p):
        return sum(cells[i] == p and any(cells[j] == 0 for j in adjacent[i]) for i in range(64))
    def potential(p):
        return sum(cells[i] == 0 and any(cells[j] == -p for j in adjacent[i]) for i in range(64))
    danger = [j for corner in CORNERS if cells[corner] == 0 for j in adjacent[corner]]
    return dict(zip(FEATURES, (
        ratio(cells.count(player), cells.count(-player)),
        ratio(len(board.legal_moves(player)), len(board.legal_moves(-player))),
        sum(cells[i] * player for i in CORNERS) / 4,
        ratio(frontier(-player), frontier(player)),
        sum(w * x * player for w, x in zip(POSITION, cells)) / POSITION_SCALE,
        ratio(potential(player), potential(-player)),
        -sum(cells[i] * player for i in danger) / 12,
    )))


@dataclass(frozen=True)
class Heuristic:
    weights: tuple[float, ...] = MANUAL_WEIGHTS

    def __post_init__(self):
        if len(self.weights) != len(FEATURES) or not all(isfinite(w) for w in self.weights):
            raise ValueError('Seven finite feature weights required')
        if sum(abs(w) for w in self.weights) == 0:
            raise ValueError('Weights cannot all be zero')

    def explain(self, board, player):
        values = features(board, player)
        scale = sum(abs(w) for w in self.weights)
        return {name: {'value': values[name], 'weight': w, 'contribution': values[name] * w / scale}
                for name, w in zip(FEATURES, self.weights)}

    def __call__(self, board, player):
        return sum(x['contribution'] for x in self.explain(board, player).values())


def terminal_value(board, player):
    # Any proven win outranks every bounded leaf; disc margin breaks winning ties.
    return 2 * board.winner() * player + sum(board.cells) * player / 64

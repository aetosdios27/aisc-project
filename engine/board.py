"""Rules implemented directly on an immutable row-major 8×8 board."""
from dataclasses import dataclass

BLACK, WHITE, EMPTY = 1, -1, 0
DIRECTIONS = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)


def coordinate(move: int) -> str:
    if type(move) is not int or not 0 <= move < 64:
        raise ValueError("Move must be an integer in [0, 63]")
    return f"{'abcdefgh'[move % 8]}{move // 8 + 1}"


def parse_move(text: str) -> int:
    if len(text) != 2 or text[0] not in 'abcdefgh' or text[1] not in '12345678':
        raise ValueError("Use a1 through h8")
    return (int(text[1]) - 1) * 8 + ord(text[0]) - ord('a')


@dataclass(frozen=True)
class Board:
    cells: tuple[int, ...]
    turn: int = BLACK
    passes: int = 0

    def __post_init__(self):
        if not isinstance(self.cells, tuple) or len(self.cells) != 64:
            raise ValueError("Board requires an immutable tuple of 64 cells")
        if any(type(x) is not int or x not in (-1, 0, 1) for x in self.cells):
            raise ValueError("Cell values must be -1, 0, or 1")
        if type(self.turn) is not int or self.turn not in (-1, 1):
            raise ValueError("Turn must be -1 or 1")
        if type(self.passes) is not int or not 0 <= self.passes <= 2:
            raise ValueError("Pass count must be 0, 1, or 2")
        if self.passes and self.legal_moves(-self.turn):
            raise ValueError("Previous player could not legally pass")
        if self.passes == 2 and self.legal_moves(self.turn):
            raise ValueError("Two passes require both players to have no move")

    @classmethod
    def initial(cls):
        cells = [0] * 64
        cells[27], cells[36] = WHITE, WHITE
        cells[28], cells[35] = BLACK, BLACK
        return cls(tuple(cells))

    def captures(self, move: int, player: int | None = None) -> tuple[int, ...]:
        player = self.turn if player is None else player
        if player not in (-1, 1):
            raise ValueError("Invalid player")
        if type(move) is not int or not 0 <= move < 64 or self.cells[move]:
            return ()
        r, c = divmod(move, 8)
        flipped = []
        for dr, dc in DIRECTIONS:
            rr, cc = r + dr, c + dc
            line = []
            while 0 <= rr < 8 and 0 <= cc < 8 and self.cells[rr * 8 + cc] == -player:
                line.append(rr * 8 + cc)
                rr, cc = rr + dr, cc + dc
            if line and 0 <= rr < 8 and 0 <= cc < 8 and self.cells[rr * 8 + cc] == player:
                flipped.extend(line)
        return tuple(flipped)

    def legal_moves(self, player: int | None = None) -> tuple[int, ...]:
        return tuple(i for i, cell in enumerate(self.cells) if not cell and self.captures(i, player))

    def is_terminal(self) -> bool:
        # Game ends as soon as neither side can play, even before explicit passes.
        return self.passes == 2 or not (self.legal_moves() or self.legal_moves(-self.turn))

    def play(self, move: int | None):
        if move is None:
            if self.legal_moves():
                raise ValueError("Passing is forbidden while a legal move exists")
            if self.passes == 2:
                raise ValueError("Game already has two passes")
            return Board(self.cells, -self.turn, self.passes + 1)
        flipped = self.captures(move)
        if not flipped or self.is_terminal():
            raise ValueError("Illegal move")
        cells = list(self.cells)
        for i in (move, *flipped):
            cells[i] = self.turn
        return Board(tuple(cells), -self.turn)

    def counts(self) -> dict[str, int]:
        return {"black": self.cells.count(BLACK), "white": self.cells.count(WHITE), "empty": self.cells.count(EMPTY)}

    def winner(self) -> int:
        if not self.is_terminal():
            raise ValueError("Winner is defined only at termination")
        diff = sum(self.cells)
        return (diff > 0) - (diff < 0)

    def serialize(self) -> str:
        return ''.join({1: 'B', -1: 'W', 0: '.'}[x] for x in self.cells) + f":{self.turn}:{self.passes}"

    @classmethod
    def deserialize(cls, text: str):
        try:
            cells, turn, passes = text.split(':')
            return cls(tuple({'B': 1, 'W': -1, '.': 0}[x] for x in cells), int(turn), int(passes))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid serialized board") from exc

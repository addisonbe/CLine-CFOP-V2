"""F2L: the four corner-edge pairs.

Each pair is inserted in turn.  A pair is solved when its corner and its edge are
home and unrotated, while the cross and every pair inserted before it stay solved.

Two mechanisms cooperate:

* a **lookup table** (``data/f2l.json``) of the 41 standard cases, whose keys are
  derived from the algorithms themselves, exactly like the OLL and PLL tables;
* a **search fallback** for configurations the table does not cover: an iterative
  deepening search guided by two admissible heuristics, the distance to insert the
  pair and the distance to restore the cross.

A table result is always verified before it is accepted, and the search is correct
by construction, so a pair is never inserted at the cost of breaking the cross or an
earlier pair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Final

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import CubieCube, move_cubie
from rubiks_cfop.cube.facelets import SOLVED_FACELETS, Face, canonicalize_colors
from rubiks_cfop.cube.moves import Move, MoveKind, get_move
from rubiks_cfop.cube.notation import format_moves, parse_moves
from rubiks_cfop.errors import SearchLimitError
from rubiks_cfop.solver.cross import cross_distance, cross_is_solved, cross_state
from rubiks_cfop.solver.tables import PHASE1_MOVE_NAMES

__all__ = [
    "PAIR_STATE_COUNT",
    "SLOTS",
    "SLOT_ORDER",
    "F2LResult",
    "PairCase",
    "PairTable",
    "Slot",
    "display_cubie",
    "load_pair_table",
    "pair_distance",
    "pair_state",
    "slot_is_solved",
    "solve_f2l",
    "solve_pair",
]

#: The order pairs are inserted in: front right, front left, back left, back right.
SLOT_ORDER: Final[tuple[str, ...]] = ("FR", "FL", "BL", "BR")

#: The four AUF adjustments.
AUF_MOVES: Final[tuple[tuple[str, ...], ...]] = ((), ("U",), ("U2",), ("U'",))

#: Deepest a pair insertion is ever searched for.
MAX_SEARCH_DEPTH: Final = 12

#: Moves the fallback search may use.  F2L never needs turns of the bottom face, and
#: leaving them out cuts the search tree noticeably.
SEARCH_MOVES: Final[tuple[str, ...]] = tuple(
    name for name in PHASE1_MOVE_NAMES if not name.startswith("D")
)

#: Number of states in the pair subproblem: 8 corners x 3 x 12 edges x 2.
PAIR_STATE_COUNT: Final = 8 * 3 * 12 * 2

#: Marker for a pair state whose distance has not been computed yet.
_UNKNOWN: Final = 255

#: Where the F2L JSON table lives.
DATA_FILE: Final = Path(__file__).resolve().parents[1] / "data" / "f2l.json"

_AXIS: Final[dict[Face, int]] = {
    Face.U: 0,
    Face.D: 0,
    Face.R: 1,
    Face.L: 1,
    Face.F: 2,
    Face.B: 2,
}


@dataclass(frozen=True, slots=True)
class Slot:
    """One F2L slot: a corner position, an edge position and a rotation.

    Attributes:
        name: ``FR``, ``FL``, ``BL`` or ``BR``.
        corner: Index of the corner position the pair belongs to.
        edge: Index of the edge position the pair belongs to.
        rotation: ``y`` turns that bring this slot to the front right.
    """

    name: str
    corner: int
    edge: int
    rotation: tuple[str, ...]


#: The four slots.  ``y`` sends the front-right slot to the front-left one, so the
#: inverse rotations bring each slot to the front right.
SLOTS: Final[dict[str, Slot]] = {
    "FR": Slot("FR", 4, 8, ()),
    "FL": Slot("FL", 5, 9, ("y'",)),
    "BL": Slot("BL", 6, 10, ("y2",)),
    "BR": Slot("BR", 7, 11, ("y",)),
}


def _encode(corner: int, corner_orientation: int, edge: int, edge_orientation: int) -> int:
    """Pack a pair subproblem state into an index."""
    return ((corner * 3 + corner_orientation) * 12 + edge) * 2 + edge_orientation


def pair_state(cubie: CubieCube, slot: Slot) -> int:
    """Return the subproblem state of one slot's two pieces."""
    corner = cubie.cp.index(slot.corner)
    edge = cubie.ep.index(slot.edge)
    return _encode(corner, cubie.co[corner], edge, cubie.eo[edge])


def slot_is_solved(cubie: CubieCube, slot: Slot) -> bool:
    """Return whether a pair is home and unrotated."""
    return (
        cubie.cp[slot.corner] == slot.corner
        and cubie.co[slot.corner] == 0
        and cubie.ep[slot.edge] == slot.edge
        and cubie.eo[slot.edge] == 0
    )


@lru_cache(maxsize=1)
def _transitions() -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Return the per-move data for the pair subproblem.

    For every move: the inverse corner permutation, the corner orientation deltas,
    the inverse edge permutation and the edge orientation deltas.  The inverse map
    turns "where does this piece go" into a lookup.
    """
    data = []
    for name in PHASE1_MOVE_NAMES:
        move = move_cubie(get_move(name))
        inverse_cp = [0] * 8
        for position, source in enumerate(move.cp):
            inverse_cp[source] = position
        inverse_ep = [0] * 12
        for position, source in enumerate(move.ep):
            inverse_ep[source] = position
        data.append((tuple(inverse_cp), move.co, tuple(inverse_ep), move.eo))
    return tuple(data)


def _step(state: int, data: tuple[tuple[int, ...], ...]) -> int:
    """Apply one move to a pair subproblem state."""
    inverse_cp, corner_delta, inverse_ep, edge_delta = data
    rest, edge_orientation = divmod(state, 2)
    rest, edge = divmod(rest, 12)
    corner, corner_orientation = divmod(rest, 3)
    target_corner = inverse_cp[corner]
    target_edge = inverse_ep[edge]
    return _encode(
        target_corner,
        (corner_orientation + corner_delta[target_corner]) % 3,
        target_edge,
        (edge_orientation + edge_delta[target_edge]) % 2,
    )


@cache
def pair_distance(slot_name: str) -> bytes:
    """Return the distance, from every pair state to an inserted pair."""
    slot = SLOTS[slot_name]
    transitions = _transitions()
    table = bytearray([_UNKNOWN]) * PAIR_STATE_COUNT
    goal = _encode(slot.corner, 0, slot.edge, 0)
    table[goal] = 0
    frontier = [goal]
    depth = 0
    while frontier:
        depth += 1
        next_frontier: list[int] = []
        append = next_frontier.append
        for state in frontier:
            for data in transitions:
                target = _step(state, data)
                if table[target] == _UNKNOWN:
                    table[target] = depth
                    append(target)
        frontier = next_frontier
    return bytes(table)


@dataclass(frozen=True, slots=True)
class PairCase:
    """One of the 41 standard F2L cases, expressed in the front-right frame."""

    label: str
    name: str
    algorithm: str
    moves: tuple[Move, ...]


@dataclass(frozen=True, slots=True)
class PairTable:
    """The F2L lookup table, with recognition keyed by pair configuration."""

    cases: dict[str, PairCase]
    keys: dict[tuple[int, int, int, int], tuple[PairCase, int]]


def display_cubie(cube: Cube) -> CubieCube:
    """Project a cube in the display frame: the faces the viewer sees.

    ``Cube.cubie`` undoes rotations, which is right for the physical puzzle but wrong
    for slot work, where "front right" means the front right of the display.
    """
    return CubieCube.from_facelets(canonicalize_colors(cube.facelets))


def _pair_key(cubie: CubieCube, corner: int, edge: int) -> tuple[int, int, int, int]:
    """Return where a pair's two pieces are, and how they are oriented."""
    corner_position = cubie.cp.index(corner)
    edge_position = cubie.ep.index(edge)
    return (
        corner_position,
        cubie.co[corner_position],
        edge_position,
        cubie.eo[edge_position],
    )


def _inverse_sequence(moves: tuple[Move, ...]) -> tuple[Move, ...]:
    """Return the sequence that undoes ``moves``."""
    return tuple(move.inverse() for move in reversed(moves))


@lru_cache(maxsize=1)
def load_pair_table() -> PairTable:
    """Build the F2L table from ``data/f2l.json``.

    The key of a case is read off the configuration its own algorithm solves, so
    recognition and execution cannot disagree.
    """
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cases: dict[str, PairCase] = {}
    keys: dict[tuple[int, int, int, int], tuple[PairCase, int]] = {}
    front_right = SLOTS["FR"]
    for entry in payload["cases"]:
        algorithm = str(entry["algorithm"])
        case = PairCase(
            label=str(entry["label"]),
            name=str(entry["name"]),
            algorithm=algorithm,
            moves=parse_moves(algorithm),
        )
        # Only face turns keep the display where it is; anything else would rotate
        # the cube and break the "cross down" convention, so those cases fall back
        # to the search instead.
        if any(move.kind is not MoveKind.FACE for move in case.moves):
            continue
        cases[case.label] = case
        for index, auf in enumerate(AUF_MOVES):
            stage = (*[get_move(name) for name in auf], *case.moves)
            state = Cube.from_facelets(SOLVED_FACELETS).apply_moves(_inverse_sequence(stage))
            key = _pair_key(display_cubie(state), front_right.corner, front_right.edge)
            keys.setdefault(key, (case, index))
    return PairTable(cases=cases, keys=keys)


@dataclass(frozen=True, slots=True)
class F2LResult:
    """One inserted pair.

    Attributes:
        slot: The slot that was filled, e.g. ``"FR"``.
        moves: The moves that inserted the pair.
        after: The cube after the insertion.
        case: The table case used, or ``None`` when the pair was inserted by search.
    """

    slot: str
    moves: tuple[Move, ...]
    after: Cube
    case: PairCase | None

    @property
    def text(self) -> str:
        """Return the insertion moves in canonical notation."""
        return format_moves(self.moves)

    @property
    def length(self) -> int:
        """Return the number of moves."""
        return len(self.moves)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of this pair."""
        return {
            "slot": self.slot,
            "moves": [move.name for move in self.moves],
            "text": self.text,
            "case": None if self.case is None else self.case.label,
            "case_name": None if self.case is None else self.case.name,
        }


def _allowed(face: Face, previous: Face | None, before: Face | None) -> bool:
    """Return whether a move may follow the last two moves."""
    if face is previous:
        return False
    if previous is None or before is None:
        return True
    return not (_AXIS[face] == _AXIS[previous] == _AXIS[before])


def _goal(cube: Cube, slot: Slot, protected: tuple[str, ...]) -> bool:
    """Return whether the cross, the earlier pairs and this pair are all solved."""
    cubie = display_cubie(cube)
    return (
        cross_is_solved(cubie)
        and slot_is_solved(cubie, slot)
        and all(slot_is_solved(cubie, SLOTS[name]) for name in protected)
    )


class _PairSearch:
    """Iterative deepening search for one pair insertion."""

    __slots__ = (
        "_cross",
        "_faces",
        "_names",
        "_protected",
        "_protected_tables",
        "_sequence",
        "_slot",
        "_table",
    )

    def __init__(self, slot: Slot, protected: tuple[str, ...]) -> None:
        self._slot = slot
        self._protected = tuple(SLOTS[name] for name in protected)
        self._table = pair_distance(slot.name)
        self._cross = cross_distance()
        self._protected_tables = tuple(pair_distance(other.name) for other in self._protected)
        self._names = SEARCH_MOVES
        self._faces = [get_move(name).face for name in self._names]
        self._sequence: list[str] = []

    def heuristic(self, cubie: CubieCube) -> int:
        """Return an admissible estimate of the moves still needed."""
        estimate = max(
            self._table[pair_state(cubie, self._slot)],
            self._cross[cross_state(cubie)],
        )
        for other, table in zip(self._protected, self._protected_tables, strict=True):
            estimate = max(estimate, table[pair_state(cubie, other)])
        return estimate

    def done(self, cubie: CubieCube) -> bool:
        """Return whether the cross, this pair and the protected pairs are solved."""
        if not cross_is_solved(cubie) or not slot_is_solved(cubie, self._slot):
            return False
        return all(slot_is_solved(cubie, other) for other in self._protected)

    def walk(
        self,
        cubie: CubieCube,
        depth: int,
        previous: Face | None,
        before: Face | None,
    ) -> bool:
        """Depth first search that returns True once the goal is reached."""
        if self.done(cubie):
            return True
        if depth == 0:
            return False
        for name, face in zip(self._names, self._faces, strict=True):
            if not _allowed(face, previous, before):
                continue
            nxt = cubie.apply(name)
            if self.heuristic(nxt) > depth - 1:
                continue
            self._sequence.append(name)
            if self.walk(nxt, depth - 1, face, previous):
                return True
            self._sequence.pop()
        return False

    def run(self, start: CubieCube) -> tuple[Move, ...]:
        """Run the search and return the insertion."""
        for bound in range(self.heuristic(start), MAX_SEARCH_DEPTH + 1):
            self._sequence.clear()
            if self.walk(start, bound, None, None):
                return tuple(get_move(name) for name in self._sequence)
        raise SearchLimitError(
            "could not insert the pair within the depth limit",
            slot=self._slot.name,
            depth=MAX_SEARCH_DEPTH,
        )


def solve_pair(
    cube: Cube,
    slot_name: str,
    *,
    protected: tuple[str, ...] = (),
) -> F2LResult:
    """Insert one pair, keeping the cross and the named slots solved.

    The lookup table is tried first, and its result is verified; the search takes
    over when the table has no case for the configuration or when the table's
    algorithm would disturb something it must not.

    Args:
        cube: The cube to work on.
        slot_name: Which slot to fill: ``FR``, ``FL``, ``BL`` or ``BR``.
        protected: Slots that must stay solved.

    Returns:
        The insertion, with the cube before and after.

    Raises:
        KeyError: If ``slot_name`` is not one of the four slots.
        SearchLimitError: If the search cannot insert the pair.
    """
    slot = SLOTS[slot_name]
    if _goal(cube, slot, protected):
        return F2LResult(slot=slot_name, moves=(), after=cube, case=None)

    table = load_pair_table()
    framed = cube.apply_moves([get_move(name) for name in slot.rotation])
    key = _pair_key(display_cubie(framed), slot.corner, slot.edge)
    match = table.keys.get(key)
    if match is not None:
        case, auf = match
        pre = [get_move(name) for name in slot.rotation]
        post = [move.inverse() for move in reversed(pre)]
        moves = (*pre, *[get_move(name) for name in AUF_MOVES[auf]], *case.moves, *post)
        after = cube.apply_moves(moves)
        if _goal(after, slot, protected):
            return F2LResult(slot=slot_name, moves=moves, after=after, case=case)

    moves = _PairSearch(slot, protected).run(display_cubie(cube))
    return F2LResult(
        slot=slot_name,
        moves=moves,
        after=cube.apply_moves(moves),
        case=None,
    )


def solve_f2l(
    cube: Cube,
    *,
    order: tuple[str, ...] = SLOT_ORDER,
) -> tuple[F2LResult, ...]:
    """Insert all four pairs, in ``order``.

    Args:
        cube: The cube, with the cross solved.
        order: The slots to fill, in the order they should be filled.

    Returns:
        One result per pair, in order.

    Raises:
        SearchLimitError: If a pair cannot be inserted.
    """
    results: list[F2LResult] = []
    current = cube
    protected: list[str] = []
    for slot_name in order:
        result = solve_pair(current, slot_name, protected=tuple(protected))
        results.append(result)
        current = result.after
        protected.append(slot_name)
    return tuple(results)

"""The cross: the first step of CFOP.

The four edges of the bottom layer are brought home, so that they line up with the
side centres they belong to.  The cross is solved optimally: a breadth first search
over the cross subproblem yields a distance table, and a solution is then read off
by walking downhill one move at a time.

The subproblem only cares about where the four bottom edges are and how they are
oriented, so its state space is small:

* which four of the twelve edge positions they occupy: ``C(12, 4) = 495``,
* which of the four pieces is in which of those positions: ``4! = 24``,
* how each of them is oriented: ``2^4 = 16``,

giving ``495 * 24 * 16 = 190,080`` states, or about a megabyte of table.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import EDGE_COUNT, CubieCube, move_cubie
from rubiks_cfop.cube.facelets import FACE_COLOR, Color, Face, canonicalize_colors
from rubiks_cfop.cube.moves import Move, get_move, rotations
from rubiks_cfop.cube.notation import format_moves
from rubiks_cfop.errors import InvalidStateError
from rubiks_cfop.solver.coordinates import (
    combination_index,
    combination_unrank,
    permutation_index,
    permutation_unrank,
)
from rubiks_cfop.solver.tables import PHASE1_MOVE_NAMES
from rubiks_cfop.solver.two_phase import simplify

__all__ = [
    "COLOR_ORDER",
    "CROSS_EDGES",
    "CROSS_STATE_COUNT",
    "SOLVED_CROSS_STATE",
    "CrossResult",
    "cross_distance",
    "cross_is_solved",
    "cross_solved_in_display",
    "cross_state",
    "rotation_to_bottom",
    "solve_best_cross",
    "solve_cross",
    "solve_cross_for_color",
]

#: The four edges of the bottom layer, in Kociemba's edge order: DR, DF, DL, DB.
CROSS_EDGES: Final[tuple[int, ...]] = (4, 5, 6, 7)

#: Which edge positions hold the cross once it is solved.
CROSS_POSITIONS: Final[tuple[int, ...]] = CROSS_EDGES

_PIECES: Final = len(CROSS_EDGES)
_ARRANGEMENTS: Final = 495 * 24
_ORIENTATIONS: Final = 1 << _PIECES
_MOVE_COUNT: Final = len(PHASE1_MOVE_NAMES)
_UNREACHED: Final = 255

#: Number of states in the cross subproblem.
CROSS_STATE_COUNT: Final = _ARRANGEMENTS * _ORIENTATIONS

#: The cross subproblem state of a solved cross.
SOLVED_CROSS_STATE: Final = combination_index(CROSS_POSITIONS, _PIECES) * 24 * 16

#: Colour order used to break ties when picking the best cross.
COLOR_ORDER: Final[tuple[Color, ...]] = (
    Color.WHITE,
    Color.YELLOW,
    Color.GREEN,
    Color.BLUE,
    Color.RED,
    Color.ORANGE,
)


def cross_state(cubie: CubieCube) -> int:
    """Encode the cross subproblem state of a cube.

    The result packs the occupied positions, the piece arrangement and the
    orientations into a single index.
    """
    positions = sorted(
        position for position in range(EDGE_COUNT) if cubie.ep[position] in CROSS_EDGES
    )
    pieces = [CROSS_EDGES.index(cubie.ep[position]) for position in positions]
    # Orientation bits are indexed by piece, so that moving a piece keeps its bit.
    orientations = 0
    for position, piece in zip(positions, pieces, strict=True):
        if cubie.eo[position]:
            orientations |= 1 << piece
    arrangement = combination_index(positions, _PIECES) * 24 + permutation_index(pieces)
    return arrangement * _ORIENTATIONS + orientations


def cross_is_solved(cubie: CubieCube) -> bool:
    """Return whether the bottom cross is solved."""
    return cross_state(cubie) == SOLVED_CROSS_STATE


#: Facelets of the four bottom edges and the centres they must match.
_BOTTOM_EDGE_CHECKS: Final[tuple[tuple[str, str], ...]] = (
    ("D2", "F5"),
    ("D4", "L5"),
    ("D6", "R5"),
    ("D8", "B5"),
)
_CENTER_CHECKS: Final[tuple[tuple[str, str], ...]] = (
    ("F8", "F5"),
    ("L8", "L5"),
    ("R8", "R5"),
    ("B8", "B5"),
)


def cross_solved_in_display(cube: Cube) -> bool:
    """Return whether the cube shows a solved cross in its bottom layer.

    This is the check a human would make: the four bottom edges carry the bottom
    colour on the bottom face, and their side stickers match the adjacent centres.
    """
    bottom = cube.facelet("D5")
    if any(cube.facelet(facelet) != bottom for facelet, _ in _BOTTOM_EDGE_CHECKS):
        return False
    return all(cube.facelet(facelet) == cube.facelet(center) for facelet, center in _CENTER_CHECKS)


@dataclass(frozen=True, slots=True)
class CrossResult:
    """A solved cross, and the orientation it was solved in.

    Attributes:
        color: The colour of the cross.
        rotation: The rotation applied to the scramble so that ``color`` is at the
            bottom; empty when the scramble already had it there.
        moves: The moves that solve the cross.
        before: The cube as the cross solver saw it, after the rotation.
        after: The cube after the cross moves, with the cross solved.
    """

    color: Color
    rotation: tuple[Move, ...]
    moves: tuple[Move, ...]
    before: Cube
    after: Cube

    @property
    def text(self) -> str:
        """Return the cross moves in canonical notation."""
        return format_moves(self.moves)

    @property
    def length(self) -> int:
        """Return the number of moves in the cross solution."""
        return len(self.moves)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of this stage."""
        return {
            "color": self.color.value,
            "rotation": format_moves(self.rotation),
            "moves": [move.name for move in self.moves],
            "text": self.text,
            "length": self.length,
        }


def _build_move_tables() -> tuple[array, bytearray]:
    """Return the arrangement transition table and the orientation flip masks.

    ``arrangement_move[a * 18 + m]`` is the arrangement reached from ``a`` by move
    ``m``, and ``orientation_flip[a * 18 + m]`` is the mask, indexed by piece, of
    the pieces whose orientation flips during that move.
    """
    moves = tuple(move_cubie(get_move(name)) for name in PHASE1_MOVE_NAMES)
    # move.ep[i] is the position a piece arrives from, so invert it to move forward.
    destinations = []
    for move in moves:
        inverse = [0] * EDGE_COUNT
        for position, source in enumerate(move.ep):
            inverse[source] = position
        destinations.append(inverse)
    arrangement_move = array("H", bytes(2 * _ARRANGEMENTS * _MOVE_COUNT))
    orientation_flip = bytearray(_ARRANGEMENTS * _MOVE_COUNT)
    for combination in range(495):
        positions = combination_unrank(combination, EDGE_COUNT, _PIECES)
        for permutation in range(24):
            pieces = permutation_unrank(permutation, _PIECES)
            base = (combination * 24 + permutation) * _MOVE_COUNT
            for offset, move in enumerate(moves):
                forward = destinations[offset]
                moved = sorted(
                    # A piece keeps its identity, lands on the position ``forward[p]``
                    # and picks up the flip recorded there.
                    (forward[positions[index]], pieces[index], move.eo[forward[positions[index]]])
                    for index in range(_PIECES)
                )
                arrangement_move[base + offset] = combination_index(
                    [entry[0] for entry in moved], _PIECES
                ) * 24 + permutation_index([entry[1] for entry in moved])
                mask = 0
                for _, piece, flip in moved:
                    if flip:
                        mask |= 1 << piece
                orientation_flip[base + offset] = mask
    return arrangement_move, orientation_flip


@lru_cache(maxsize=1)
def _move_tables() -> tuple[array, bytearray]:
    """Return the cached cross move tables."""
    return _build_move_tables()


@lru_cache(maxsize=1)
def cross_distance() -> bytes:
    """Return the distance, in moves, from every cross state to a solved cross."""
    arrangement_move, orientation_flip = _move_tables()
    table = bytearray([_UNREACHED]) * CROSS_STATE_COUNT
    table[SOLVED_CROSS_STATE] = 0
    frontier = [SOLVED_CROSS_STATE]
    depth = 0
    while frontier:
        depth += 1
        next_frontier: list[int] = []
        append = next_frontier.append
        for state in frontier:
            arrangement, orientations = divmod(state, _ORIENTATIONS)
            base = arrangement * _MOVE_COUNT
            for offset in range(_MOVE_COUNT):
                target = arrangement_move[base + offset] * _ORIENTATIONS + (
                    orientations ^ orientation_flip[base + offset]
                )
                if table[target] == _UNREACHED:
                    table[target] = depth
                    append(target)
        frontier = next_frontier
    return bytes(table)


def solve_cross(cubie: CubieCube) -> tuple[Move, ...]:
    """Return a shortest sequence of face moves that solves the cross.

    Args:
        cubie: The state to solve; its centres decide which cross is meant.

    Returns:
        The moves, in order.  Empty when the cross is already solved.
    """
    arrangement_move, orientation_flip = _move_tables()
    distances = cross_distance()
    state = cross_state(cubie)
    solution: list[Move] = []

    while distances[state]:
        arrangement, orientations = divmod(state, _ORIENTATIONS)
        base = arrangement * _MOVE_COUNT
        wanted = distances[state] - 1
        for offset, name in enumerate(PHASE1_MOVE_NAMES):
            target = arrangement_move[base + offset] * _ORIENTATIONS + (
                orientations ^ orientation_flip[base + offset]
            )
            if distances[target] == wanted:
                solution.append(get_move(name))
                state = target
                break
        else:  # pragma: no cover - the distance table guarantees a downhill move
            raise InvalidStateError("no downhill move found while solving the cross")
    return tuple(get_move(name) for name in simplify([move.name for move in solution]))


@lru_cache(maxsize=1)
def _rotations_to_bottom() -> dict[Color, tuple[Move, ...]]:
    """Map each colour to a rotation that brings it to the bottom face."""
    lookup: dict[Color, tuple[Move, ...]] = {}
    for sequence in rotations():
        state = Cube.solved()
        for name in sequence:
            state = state.apply(name)
        center = Face(state.face_facelets(Face.D)[4])
        lookup.setdefault(FACE_COLOR[center], tuple(get_move(name) for name in sequence))
    return lookup


def rotation_to_bottom(color: Color) -> tuple[Move, ...]:
    """Return a rotation that brings ``color`` to the bottom face."""
    return _rotations_to_bottom()[Color(color)]


def solve_cross_for_color(cube: Cube, color: Color | str) -> CrossResult:
    """Solve the cross of a chosen colour, in the bottom layer.

    The cube is first rotated so that ``color`` ends up on the bottom face, which
    is the orientation the rest of the CFOP solve works in.

    Args:
        cube: The scrambled cube.
        color: The colour of the cross, for example ``"white"``.

    Returns:
        The rotation applied, the cross moves, and the cube before and after.
    """
    resolved = Color(color)
    rotation = _rotations_to_bottom()[resolved]
    reoriented = cube.apply_moves(rotation)
    # Name the faces the way the viewer sees them, so that the cross table's "D
    # layer" means the displayed bottom layer and "D" means the chosen colour.
    frame = CubieCube.from_facelets(canonicalize_colors(reoriented.facelets))
    moves = solve_cross(frame)
    return CrossResult(
        color=resolved,
        rotation=rotation,
        moves=moves,
        before=reoriented,
        after=reoriented.apply_moves(moves),
    )


def solve_best_cross(
    cube: Cube,
    *,
    colors: tuple[Color, ...] | None = None,
) -> CrossResult:
    """Solve whichever cross needs the fewest moves.

    Ties are broken by the order of :data:`COLOR_ORDER`, so the result is stable.

    Args:
        cube: The scrambled cube.
        colors: The colours to consider; all six by default.

    Returns:
        The best cross, with the rotation that was applied to reach it.
    """
    candidates = COLOR_ORDER if colors is None else colors
    best: CrossResult | None = None
    for color in candidates:
        candidate = solve_cross_for_color(cube, color)
        if best is None or candidate.length < best.length:
            best = candidate
    if best is None:  # pragma: no cover - COLOR_ORDER is never empty
        raise InvalidStateError("no cross colours to try")
    return best

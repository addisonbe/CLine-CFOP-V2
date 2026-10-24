"""Move and pruning tables for the two-phase solver.

Building the tables costs a few seconds of CPU, so they are constructed lazily on
first use and cached for the lifetime of the process.  :func:`preload` lets a GUI
pay that cost on a background thread at startup instead of on the first solve.

Memory: about 2 MB of move tables and 4 MB of pruning tables.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from rubiks_cfop.cube.cubie import CORNER_COUNT, EDGE_COUNT, CubieCube, move_cubie
from rubiks_cfop.cube.facelets import FACE_ORDER
from rubiks_cfop.cube.moves import get_move
from rubiks_cfop.solver.coordinates import (
    CORNER_PERM_COUNT,
    EDGE_PERM_COUNT,
    FLIP_COUNT,
    SLICE_COUNT,
    SLICE_PERM_COUNT,
    SOLVED_SLICE,
    TWIST_COUNT,
    UD_EDGE_COUNT,
    combination_index,
    combination_unrank,
    permutation_index,
    permutation_unrank,
)

__all__ = [
    "PHASE1_MOVE_NAMES",
    "PHASE2_MOVE_NAMES",
    "SolverTables",
    "preload",
    "solver_tables",
]

#: The 18 face turns, in a fixed order that the move tables are indexed by.
PHASE1_MOVE_NAMES: Final[tuple[str, ...]] = tuple(
    f"{face.value}{suffix}" for face in FACE_ORDER for suffix in ("", "2", "'")
)

#: The moves that keep the phase-1 coordinates solved: half turns of R, L, F, B
#: and every turn of U and D.
PHASE2_MOVE_NAMES: Final[tuple[str, ...]] = (
    "U",
    "U2",
    "U'",
    "D",
    "D2",
    "D'",
    "R2",
    "L2",
    "F2",
    "B2",
)

_UNREACHED: Final = 255


@dataclass(frozen=True, slots=True)
class SolverTables:
    """Every table the two-phase search needs.

    Move tables are flat arrays indexed by ``coordinate * len(moves) + move``.
    Pruning tables are flat byte strings indexed by the combined coordinate and
    hold the distance to the goal, in moves.
    """

    twist_move: array
    flip_move: array
    slice_move: array
    corner_perm_move: array
    edge_perm_move: array
    slice_perm_move: array
    prune_twist_slice: bytes
    prune_flip_slice: bytes
    prune_corner_perm_slice_perm: bytes
    prune_edge_perm_slice_perm: bytes


def _move_cubies(names: tuple[str, ...]) -> tuple[CubieCube, ...]:
    """Return the cubie level effect of each move name."""
    return tuple(move_cubie(get_move(name)) for name in names)


def _build_twist_move(moves: tuple[CubieCube, ...]) -> array:
    """Corner orientation after each phase-1 move, for every orientation."""
    table = array("H", bytes(2 * TWIST_COUNT * len(moves)))
    for value in range(TWIST_COUNT):
        co = [0] * CORNER_COUNT
        total = 0
        remaining = value
        for index in range(CORNER_COUNT - 1):
            co[index] = remaining % 3
            total += co[index]
            remaining //= 3
        co[CORNER_COUNT - 1] = (-total) % 3
        base = value * len(moves)
        for offset, move in enumerate(moves):
            target = 0
            weight = 1
            for index in range(CORNER_COUNT - 1):
                target += ((co[move.cp[index]] + move.co[index]) % 3) * weight
                weight *= 3
            table[base + offset] = target
    return table


def _build_flip_move(moves: tuple[CubieCube, ...]) -> array:
    """Edge orientation after each phase-1 move, for every orientation."""
    table = array("H", bytes(2 * FLIP_COUNT * len(moves)))
    for value in range(FLIP_COUNT):
        eo = [0] * EDGE_COUNT
        total = 0
        remaining = value
        for index in range(EDGE_COUNT - 1):
            eo[index] = remaining % 2
            total += eo[index]
            remaining //= 2
        eo[EDGE_COUNT - 1] = total % 2
        base = value * len(moves)
        for offset, move in enumerate(moves):
            target = 0
            weight = 1
            for index in range(EDGE_COUNT - 1):
                target += ((eo[move.ep[index]] + move.eo[index]) % 2) * weight
                weight *= 2
            table[base + offset] = target
    return table


def _build_slice_move(moves: tuple[CubieCube, ...]) -> array:
    """Slice position after each phase-1 move, for every slice arrangement."""
    table = array("H", bytes(2 * SLICE_COUNT * len(moves)))
    for value in range(SLICE_COUNT):
        occupied = set(combination_unrank(value, EDGE_COUNT, 4))
        base = value * len(moves)
        for offset, move in enumerate(moves):
            moved = {position for position in range(EDGE_COUNT) if move.ep[position] in occupied}
            table[base + offset] = combination_index(moved, 4)
    return table


def _build_permutation_move(
    count: int,
    size: int,
    moves: tuple[CubieCube, ...],
    source: str,
    offset: int = 0,
) -> array:
    """Permutation coordinate after each phase-2 move, for every permutation.

    Args:
        count: Number of coordinate values.
        size: Number of pieces the coordinate describes.
        moves: The phase-2 moves.
        source: Which cubie permutation to read, ``"corner"`` or ``"edge"``.
        offset: Index of the first piece, for the slice permutation.
    """
    table = array("H", bytes(2 * count * len(moves)))
    for value in range(count):
        permutation = permutation_unrank(value, size)
        base = value * len(moves)
        for move_offset, move in enumerate(moves):
            mapping = move.cp if source == "corner" else move.ep
            moved = [permutation[mapping[offset + index] - offset] for index in range(size)]
            table[base + move_offset] = permutation_index(moved)
    return table


@dataclass(frozen=True, slots=True)
class _PruneRequest:
    """What a pruning table describes: a pair of coordinates and its goal."""

    first_move: array
    second_move: array
    first_count: int
    second_count: int
    first_goal: int
    second_goal: int
    move_count: int


def _build_pruning_two(request: _PruneRequest) -> bytes:
    """Breadth first search over a pair of coordinates.

    The result is the distance, in moves, from each coordinate pair to the goal,
    with 255 marking states that cannot be reached.
    """
    first_move = request.first_move
    second_move = request.second_move
    first_count = request.first_count
    second_count = request.second_count
    first_goal = request.first_goal
    second_goal = request.second_goal
    move_count = request.move_count
    table = bytearray([_UNREACHED]) * (first_count * second_count)
    table[first_goal * second_count + second_goal] = 0
    frontier = [(first_goal, second_goal)]
    depth = 0
    while frontier:
        depth += 1
        next_frontier: list[tuple[int, int]] = []
        append = next_frontier.append
        for first, second in frontier:
            first_base = first * move_count
            second_base = second * move_count
            for offset in range(move_count):
                new_first = first_move[first_base + offset]
                new_second = second_move[second_base + offset]
                index = new_first * second_count + new_second
                if table[index] == _UNREACHED:
                    table[index] = depth
                    append((new_first, new_second))
        frontier = next_frontier
    return bytes(table)


def _build_tables() -> SolverTables:
    """Build every table.  Slow: a few seconds of CPU."""
    phase1 = _move_cubies(PHASE1_MOVE_NAMES)
    phase2 = _move_cubies(PHASE2_MOVE_NAMES)

    twist_move = _build_twist_move(phase1)
    flip_move = _build_flip_move(phase1)
    slice_move = _build_slice_move(phase1)
    corner_perm_move = _build_permutation_move(CORNER_PERM_COUNT, CORNER_COUNT, phase2, "corner")
    edge_perm_move = _build_permutation_move(EDGE_PERM_COUNT, UD_EDGE_COUNT, phase2, "edge")
    slice_perm_move = _build_permutation_move(
        SLICE_PERM_COUNT,
        EDGE_COUNT - UD_EDGE_COUNT,
        phase2,
        "edge",
        offset=UD_EDGE_COUNT,
    )

    return SolverTables(
        twist_move=twist_move,
        flip_move=flip_move,
        slice_move=slice_move,
        corner_perm_move=corner_perm_move,
        edge_perm_move=edge_perm_move,
        slice_perm_move=slice_perm_move,
        prune_twist_slice=_build_pruning_two(
            _PruneRequest(
                twist_move, slice_move, TWIST_COUNT, SLICE_COUNT, 0, SOLVED_SLICE, len(phase1)
            )
        ),
        prune_flip_slice=_build_pruning_two(
            _PruneRequest(
                flip_move, slice_move, FLIP_COUNT, SLICE_COUNT, 0, SOLVED_SLICE, len(phase1)
            )
        ),
        prune_corner_perm_slice_perm=_build_pruning_two(
            _PruneRequest(
                corner_perm_move,
                slice_perm_move,
                CORNER_PERM_COUNT,
                SLICE_PERM_COUNT,
                0,
                0,
                len(phase2),
            )
        ),
        prune_edge_perm_slice_perm=_build_pruning_two(
            _PruneRequest(
                edge_perm_move,
                slice_perm_move,
                EDGE_PERM_COUNT,
                SLICE_PERM_COUNT,
                0,
                0,
                len(phase2),
            )
        ),
    )


@lru_cache(maxsize=1)
def solver_tables() -> SolverTables:
    """Return the shared tables, building them on first use."""
    return _build_tables()


def preload() -> None:
    """Build the tables now, so that a later solve does not pay for them."""
    solver_tables()

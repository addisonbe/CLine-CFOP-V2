"""A Kociemba style two-phase solver.

The cube is solved in two stages:

1. bring the corner orientations, the edge orientations and the four slice edges
   home, using all 18 face turns;
2. solve the remaining permutation using only half turns of R, L, F and B plus any
   turn of U and D, which cannot disturb what phase 1 fixed.

Each phase is an iterative deepening depth first search guided by a pair of
breadth-first pruning tables, so it finds a solution quickly without needing an
optimal one.  A whole solve is typically 20 to 24 moves.

The solver is used for two things: producing the random-state scrambles that WCA
Regulation 4b3 requires, and acting as an independent oracle that the CFOP pipeline
is checked against in the later stages.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.facelets import Face
from rubiks_cfop.cube.moves import get_move
from rubiks_cfop.errors import CancelledError, SearchLimitError, SolveTimeoutError
from rubiks_cfop.solver.coordinates import (
    SLICE_COUNT,
    SLICE_PERM_COUNT,
    SOLVED_SLICE,
    corner_perm,
    edge_perm,
    flip,
    slice_perm,
    slice_position,
    twist,
)
from rubiks_cfop.solver.tables import (
    PHASE1_MOVE_NAMES,
    PHASE2_MOVE_NAMES,
    SolverTables,
    solver_tables,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rubiks_cfop.cancel import CancelToken
    from rubiks_cfop.cube.cubie import CubieCube

__all__ = ["SearchLimits", "simplify", "solve"]

#: How many search nodes to run between cancellation checks.
_CHECK_INTERVAL: Final = 256


@dataclass(frozen=True, slots=True)
class SearchLimits:
    """Bounds for a two-phase search.

    Attributes:
        max_phase1_depth: Largest number of moves allowed in phase 1.
        max_phase2_depth: Largest number of moves allowed in phase 2.
        max_total_depth: Largest number of moves allowed in total.
        timeout_ms: Wall clock budget in milliseconds, or ``None`` for no limit.
    """

    max_phase1_depth: int = 12
    max_phase2_depth: int = 18
    max_total_depth: int = 30
    timeout_ms: int | None = None


class _Search:
    """State shared by one solve: tables, limits, cancellation and a clock."""

    __slots__ = ("_cancel", "_deadline", "_nodes", "limits", "tables")

    def __init__(
        self,
        tables: SolverTables,
        limits: SearchLimits,
        cancel: CancelToken | None,
    ) -> None:
        self.tables = tables
        self.limits = limits
        self._cancel = cancel
        self._nodes = 0
        self._deadline = (
            None if limits.timeout_ms is None else time.monotonic() + limits.timeout_ms / 1000
        )

    def tick(self) -> None:
        """Check the cancellation flag and the deadline every so often."""
        self._nodes += 1
        if self._nodes % _CHECK_INTERVAL:
            return
        if self._cancel is not None and self._cancel.cancelled:
            raise CancelledError("the solve was cancelled")
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise SolveTimeoutError("the solve ran out of time", nodes=self._nodes)


def _face_of(name: str) -> Face:
    """Return the face a phase-1 or phase-2 move turns."""
    face = get_move(name).face
    if face is None:  # pragma: no cover - both move sets are face turns
        raise AssertionError(f"{name} is not a face turn")
    return face


_FACE_OF: Final[dict[str, Face]] = {name: _face_of(name) for name in PHASE1_MOVE_NAMES}

_AXIS: Final[dict[Face, int]] = {
    Face.U: 0,
    Face.D: 0,
    Face.R: 1,
    Face.L: 1,
    Face.F: 2,
    Face.B: 2,
}


def _allowed(name: str, previous: Face | None, before_that: Face | None) -> bool:
    """Return whether a move may follow the last two moves.

    The usual scramble style filters: never the same face twice in a row, and
    never three moves in a row on one axis.
    """
    face = _FACE_OF[name]
    if face is previous:
        return False
    if previous is None or before_that is None:
        return True
    return not (_AXIS[face] == _AXIS[previous] == _AXIS[before_that])


def _phase1_solutions(
    search: _Search,
    coordinates: tuple[int, int, int],
    max_depth: int,
) -> Iterator[tuple[str, ...]]:
    """Yield every phase-1 solution of exactly ``max_depth`` moves, in move order.

    ``coordinates`` is the ``(twist, flip, slice)`` triple.
    """
    tables = search.tables
    twist_move = tables.twist_move
    flip_move = tables.flip_move
    slice_move = tables.slice_move
    prune_twist = tables.prune_twist_slice
    prune_flip = tables.prune_flip_slice
    names = PHASE1_MOVE_NAMES
    move_count = len(names)
    sequence: list[str] = []
    goal = (0, 0, SOLVED_SLICE)

    def walk(
        depth: int,
        state: tuple[int, int, int],
        previous: Face | None,
        before_that: Face | None,
    ) -> Iterator[tuple[str, ...]]:
        search.tick()
        if depth == max_depth:
            if state == goal:
                yield tuple(sequence)
            return
        current_twist, current_flip, current_slice = state
        twist_base = current_twist * move_count
        flip_base = current_flip * move_count
        slice_base = current_slice * move_count
        for offset, name in enumerate(names):
            if not _allowed(name, previous, before_that):
                continue
            next_twist = twist_move[twist_base + offset]
            next_flip = flip_move[flip_base + offset]
            next_slice = slice_move[slice_base + offset]
            estimate = prune_twist[next_twist * SLICE_COUNT + next_slice]
            estimate = max(estimate, prune_flip[next_flip * SLICE_COUNT + next_slice])
            if depth + 1 + estimate > max_depth:
                continue
            sequence.append(name)
            yield from walk(
                depth + 1,
                (next_twist, next_flip, next_slice),
                _FACE_OF[name],
                previous,
            )
            sequence.pop()

    yield from walk(0, coordinates, None, None)


def _phase2_search(
    search: _Search,
    coordinates: tuple[int, int, int],
    max_depth: int,
) -> tuple[str, ...] | None:
    """Return a phase-2 solution of at most ``max_depth`` moves, if there is one.

    ``coordinates`` is the ``(corner permutation, edge permutation, slice
    permutation)`` triple.
    """
    tables = search.tables
    corner_move = tables.corner_perm_move
    edge_move = tables.edge_perm_move
    slice_move = tables.slice_perm_move
    prune_corner = tables.prune_corner_perm_slice_perm
    prune_edge = tables.prune_edge_perm_slice_perm
    names = PHASE2_MOVE_NAMES
    move_count = len(names)
    sequence: list[str] = []

    def walk(
        depth: int,
        state: tuple[int, int, int],
        previous: Face | None,
        before_that: Face | None,
        limit: int,
    ) -> bool:
        search.tick()
        if state == (0, 0, 0):
            return True
        if depth == limit:  # pragma: no cover - the pruning bound already stops here
            # Defensive: the pruning table guarantees that a node at the depth limit
            # has distance zero, so it is caught by the check above.
            return False
        current_corner, current_edge, current_slice = state
        corner_base = current_corner * move_count
        edge_base = current_edge * move_count
        slice_base = current_slice * move_count
        for offset, name in enumerate(names):
            if not _allowed(name, previous, before_that):
                continue
            next_corner = corner_move[corner_base + offset]
            next_edge = edge_move[edge_base + offset]
            next_slice = slice_move[slice_base + offset]
            estimate = prune_corner[next_corner * SLICE_PERM_COUNT + next_slice]
            estimate = max(estimate, prune_edge[next_edge * SLICE_PERM_COUNT + next_slice])
            if depth + 1 + estimate > limit:
                continue
            sequence.append(name)
            if walk(
                depth + 1,
                (next_corner, next_edge, next_slice),
                _FACE_OF[name],
                previous,
                limit,
            ):
                return True
            sequence.pop()
        return False

    lower_bound = max(
        prune_corner[coordinates[0] * SLICE_PERM_COUNT + coordinates[2]],
        prune_edge[coordinates[1] * SLICE_PERM_COUNT + coordinates[2]],
    )
    for limit in range(lower_bound, max_depth + 1):
        sequence.clear()
        if walk(0, coordinates, None, None, limit):
            return tuple(sequence)
    return None


def simplify(names: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Cancel adjacent turns of the same face.

    Phase 1 and phase 2 are searched independently, so the join between them can
    contain a redundant pair such as ``R2 R2`` or ``R R'``.
    """
    result: list[str] = []
    for name in names:
        if result and result[-1][0] == name[0]:
            previous = result.pop()
            turns = (get_move(previous).turns + get_move(name).turns) % 4
            if turns:
                suffix = {1: "", 2: "2", 3: "'"}[turns]
                result.append(f"{name[0]}{suffix}")
        else:
            result.append(name)
    return tuple(result)


def solve(
    cubie: CubieCube,
    *,
    limits: SearchLimits | None = None,
    cancel: CancelToken | None = None,
) -> tuple[str, ...]:
    """Return a sequence of face moves that solves ``cubie``.

    Args:
        cubie: The state to solve.
        limits: Depth and time bounds; defaults to :class:`SearchLimits`.
        cancel: Optional token that aborts the search when set.

    Returns:
        The solution, as canonical move names.  Empty for a solved cube.

    Raises:
        InvalidStateError: If the state is malformed.
        UnsolvableStateError: If the state cannot occur on a real cube.
        SearchLimitError: If no solution was found inside the depth limits.
        SolveTimeoutError: If the deadline passed.
        CancelledError: If the token was cancelled.
    """
    resolved = limits or SearchLimits()
    cubie.validate()
    if cubie.is_solved():
        return ()

    search = _Search(solver_tables(), resolved, cancel)
    twist_value = twist(cubie)
    flip_value = flip(cubie)
    slice_value = slice_position(cubie)
    lower_bound = max(
        search.tables.prune_twist_slice[twist_value * SLICE_COUNT + slice_value],
        search.tables.prune_flip_slice[flip_value * SLICE_COUNT + slice_value],
    )

    # Phase 1 cannot be longer than the whole budget, so a small total budget also
    # bounds how deep phase 1 is allowed to search.  That invariant also means the
    # phase-2 budget below can never go negative.
    phase1_limit = min(resolved.max_phase1_depth, resolved.max_total_depth)
    for depth in range(lower_bound, phase1_limit + 1):
        for sequence in _phase1_solutions(search, (twist_value, flip_value, slice_value), depth):
            state = cubie.apply_moves(sequence)
            remaining = min(
                resolved.max_phase2_depth,
                resolved.max_total_depth - len(sequence),
            )
            phase2 = _phase2_search(
                search,
                (corner_perm(state), edge_perm(state), slice_perm(state)),
                remaining,
            )
            if phase2 is not None:
                return simplify((*sequence, *phase2))

    raise SearchLimitError(
        "no solution inside the depth limits",
        max_phase1_depth=resolved.max_phase1_depth,
        max_phase2_depth=resolved.max_phase2_depth,
        max_total_depth=resolved.max_total_depth,
    )

"""The two-phase solver: correctness, limits, cancellation and table integrity."""

from __future__ import annotations

import itertools
import random

import pytest

from rubiks_cfop.cancel import CancelToken
from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.moves import MOVES, get_move
from rubiks_cfop.errors import (
    CancelledError,
    SearchLimitError,
    SolveTimeoutError,
    UnsolvableStateError,
)
from rubiks_cfop.solver import preload
from rubiks_cfop.solver.coordinates import (
    SLICE_COUNT,
    SLICE_PERM_COUNT,
    SOLVED_SLICE,
    corner_perm,
    edge_perm,
    flip,
    permutation_unrank,
    slice_perm,
    slice_position,
    twist,
)
from rubiks_cfop.solver.tables import (
    PHASE1_MOVE_NAMES,
    PHASE2_MOVE_NAMES,
    solver_tables,
)
from rubiks_cfop.solver.two_phase import (
    SearchLimits,
    _phase2_search,
    _Search,
    simplify,
    solve,
)

FACE_MOVES = [name for name in MOVES if MOVES[name].kind == "face"]


@pytest.fixture(scope="module")
def random_states() -> list[CubieCube]:
    """A handful of deterministic scrambled states."""
    rng = random.Random(20261024)
    return [
        CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
        for _ in range(10)
    ]


def test_move_sets_are_face_turns() -> None:
    assert len(PHASE1_MOVE_NAMES) == 18
    assert len(PHASE2_MOVE_NAMES) == 10
    assert all(MOVES[name].kind == "face" for name in PHASE1_MOVE_NAMES)
    assert all(MOVES[name].kind == "face" for name in PHASE2_MOVE_NAMES)
    assert all(name.endswith("2") or name[0] in "UD" for name in PHASE2_MOVE_NAMES)


def test_phase_two_moves_preserve_phase_one_coordinates() -> None:
    phase_one_state = CubieCube(
        cp=tuple(range(8)),
        co=(0,) * 8,
        ep=(*range(8), 8, 9, 10, 11),
        eo=(0,) * 12,
    )
    assert twist(phase_one_state) == 0
    assert flip(phase_one_state) == 0
    assert slice_position(phase_one_state) == SOLVED_SLICE
    for name in PHASE2_MOVE_NAMES:
        moved = phase_one_state.apply(name)
        assert twist(moved) == 0, name
        assert flip(moved) == 0, name
        assert slice_position(moved) == SOLVED_SLICE, name


def test_tables_have_expected_shape_and_depths() -> None:
    tables = solver_tables()
    assert len(tables.prune_twist_slice) == 2187 * SLICE_COUNT
    assert len(tables.prune_flip_slice) == 2048 * SLICE_COUNT
    assert len(tables.prune_corner_perm_slice_perm) == 40320 * SLICE_PERM_COUNT
    assert len(tables.prune_edge_perm_slice_perm) == 40320 * SLICE_PERM_COUNT
    # The classic phase-1 depths: 9 moves are needed for the worst cases.
    assert max(tables.prune_twist_slice) == 9
    assert max(tables.prune_flip_slice) == 9
    assert 255 not in tables.prune_twist_slice
    assert 255 not in tables.prune_flip_slice


def test_tables_are_shared() -> None:
    assert solver_tables() is solver_tables()


def test_preload_builds_the_tables() -> None:
    preload()
    assert solver_tables() is solver_tables()


def test_phase_one_move_tables_match_direct_application() -> None:
    """The incrementally built tables must agree with applying the moves for real."""
    tables = solver_tables()
    rng = random.Random(2027)
    for _ in range(20):
        state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(12)])
        for offset, name in enumerate(PHASE1_MOVE_NAMES):
            moved = state.apply(name)
            assert tables.twist_move[twist(state) * 18 + offset] == twist(moved), name
            assert tables.flip_move[flip(state) * 18 + offset] == flip(moved), name
            assert tables.slice_move[slice_position(state) * 18 + offset] == slice_position(moved)


def test_phase_two_move_tables_match_direct_application() -> None:
    tables = solver_tables()
    rng = random.Random(2028)
    for _ in range(20):
        state = CubieCube.solved().apply_moves([rng.choice(PHASE2_MOVE_NAMES) for _ in range(12)])
        for offset, name in enumerate(PHASE2_MOVE_NAMES):
            moved = state.apply(name)
            assert tables.corner_perm_move[corner_perm(state) * 10 + offset] == corner_perm(moved)
            assert tables.edge_perm_move[edge_perm(state) * 10 + offset] == edge_perm(moved)
            assert tables.slice_perm_move[slice_perm(state) * 10 + offset] == slice_perm(moved)


def test_solved_cube_needs_no_moves() -> None:
    assert solve(CubieCube.solved()) == ()


@pytest.mark.parametrize("index", range(10))
def test_solver_solves_random_states(random_states: list[CubieCube], index: int) -> None:
    state = random_states[index]
    solution = solve(state)
    assert state.apply_moves(solution).is_solved()
    assert len(solution) <= SearchLimits().max_total_depth
    assert all(get_move(name).kind == "face" for name in solution)


def test_solution_has_no_redundant_pairs(random_states: list[CubieCube]) -> None:
    for state in random_states[:5]:
        solution = solve(state)
        assert solution == simplify(solution)
        for first, second in itertools.pairwise(solution):
            assert first[0] != second[0]


def test_solver_is_deterministic(random_states: list[CubieCube]) -> None:
    state = random_states[0]
    assert solve(state) == solve(state)


def test_solver_rejects_unsolvable_states() -> None:
    twisted = CubieCube(
        cp=tuple(range(8)), co=(1, 0, 0, 0, 0, 0, 0, 0), ep=tuple(range(12)), eo=(0,) * 12
    )
    with pytest.raises(UnsolvableStateError):
        solve(twisted)


def test_tight_limits_raise_search_limit_error() -> None:
    rng = random.Random(5)
    state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    with pytest.raises(SearchLimitError, match="no solution inside the depth limits"):
        solve(state, limits=SearchLimits(max_phase1_depth=2, max_phase2_depth=2, max_total_depth=4))


def test_cancellation_is_honoured() -> None:
    rng = random.Random(6)
    state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    token = CancelToken()
    token.cancel()
    with pytest.raises(CancelledError, match="cancelled"):
        solve(state, cancel=token)


def test_cancel_token_reset_clears_the_flag() -> None:
    token = CancelToken()
    assert not token.cancelled
    token.cancel()
    assert token.cancelled
    token.reset()
    assert not token.cancelled


def test_phase_two_limit_is_reported_as_a_search_limit() -> None:
    """A phase-2 budget that is too small must fail cleanly, not silently."""
    rng = random.Random(61)
    state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    with pytest.raises(SearchLimitError):
        solve(state, limits=SearchLimits(max_phase1_depth=3, max_phase2_depth=2, max_total_depth=6))


def test_total_limit_smaller_than_phase_one_is_reported() -> None:
    """Phase-1 solutions longer than the total budget are skipped, not used."""
    rng = random.Random(62)
    state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    with pytest.raises(SearchLimitError):
        solve(
            state, limits=SearchLimits(max_phase1_depth=6, max_phase2_depth=18, max_total_depth=4)
        )


def test_timeout_is_honoured() -> None:
    rng = random.Random(7)
    state = CubieCube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    with pytest.raises(SolveTimeoutError, match="ran out of time"):
        solve(
            state,
            limits=SearchLimits(max_phase1_depth=12, max_phase2_depth=18, timeout_ms=0),
        )


def test_simplify_cancels_adjacent_turns() -> None:
    assert simplify(["R", "R"]) == ("R2",)
    assert simplify(["R", "R'"]) == ()
    assert simplify(["R2", "R2"]) == ()
    assert simplify(["R", "R", "R"]) == ("R'",)
    assert simplify(["R", "U", "U2"]) == ("R", "U'")
    assert simplify(["R", "U", "F"]) == ("R", "U", "F")
    assert simplify([]) == ()


def _permutation_parity(rank: int, size: int) -> int:
    """Return the parity of the permutation with a given rank."""
    permutation = permutation_unrank(rank, size)
    inversions = sum(
        1
        for index, value in enumerate(permutation)
        for other in permutation[index + 1 :]
        if other < value
    )
    return inversions % 2


def test_phase_two_search_gives_up_inside_a_tight_limit() -> None:
    """A phase-2 search that runs out of depth must report failure, not hang."""
    tables = solver_tables()
    search = _Search(tables, SearchLimits(), None)
    for corner in range(1, 60):
        for edge in range(5):
            # Only reachable combinations: the two permutations must share a parity.
            if _permutation_parity(corner, 8) != _permutation_parity(edge, 8):
                continue
            coordinates = (corner, edge, 0)
            bound = max(
                tables.prune_corner_perm_slice_perm[corner * SLICE_PERM_COUNT],
                tables.prune_edge_perm_slice_perm[edge * SLICE_PERM_COUNT],
            )
            if bound == 0:
                continue
            if _phase2_search(search, coordinates, bound) is not None:
                continue  # the heuristic happened to be exact here
            for limit in range(bound + 1, bound + 4):
                if _phase2_search(search, coordinates, limit) is not None:
                    return  # the failure path was exercised and then recovered
    pytest.fail("no state needed more moves than its heuristic suggested")

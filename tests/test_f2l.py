"""F2L: pair subproblem, table cases and full two-layer solves."""

from __future__ import annotations

import random

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.moves import MOVES
from rubiks_cfop.solver.cross import solve_best_cross
from rubiks_cfop.solver.f2l import (
    PAIR_STATE_COUNT,
    SLOT_ORDER,
    SLOTS,
    PairCase,
    display_cubie,
    load_pair_table,
    pair_distance,
    pair_state,
    slot_is_solved,
    solve_f2l,
    solve_pair,
)

FACE_MOVES = [name for name in MOVES if MOVES[name].kind == "face"]


def two_layers_solved(cube: Cube) -> bool:
    """Return whether the bottom layer and the middle layer are solved."""
    cubie = display_cubie(cube)
    return (
        cubie.cp[4:8] == (4, 5, 6, 7)
        and cubie.co[4:8] == (0, 0, 0, 0)
        and cubie.ep[4:8] == (4, 5, 6, 7)
        and cubie.eo[4:8] == (0, 0, 0, 0)
        and cubie.ep[8:12] == (8, 9, 10, 11)
        and cubie.eo[8:12] == (0, 0, 0, 0)
    )


def cross_solved_cubes(count: int, *, seed: int = 4242) -> list[Cube]:
    """Return random cubes with the cross solved."""
    rng = random.Random(seed)
    cubes = []
    for _ in range(count):
        scrambled = Cube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
        cubes.append(solve_best_cross(scrambled).after)
    return cubes


def test_slot_definitions() -> None:
    assert set(SLOTS) == set(SLOT_ORDER)
    assert SLOTS["FR"].corner == 4
    assert SLOTS["FR"].edge == 8
    assert SLOTS["BR"].corner == 7
    assert SLOTS["BR"].edge == 11
    assert SLOTS["FR"].rotation == ()
    assert all(slot.rotation for name, slot in SLOTS.items() if name != "FR")


def test_pair_state_and_solved_check() -> None:
    solved = CubieCube.solved()
    # The solved front-right pair: corner 4 at position 4, edge 8 at position 8.
    assert pair_state(solved, SLOTS["FR"]) == ((4 * 3 + 0) * 12 + 8) * 2
    assert slot_is_solved(solved, SLOTS["FR"])
    moved = solved.apply("R")
    assert not slot_is_solved(moved, SLOTS["FR"])
    assert 0 <= pair_state(moved, SLOTS["FR"]) < PAIR_STATE_COUNT


@pytest.mark.parametrize("slot_name", SLOT_ORDER)
def test_pair_distance_tables_are_complete(slot_name: str) -> None:
    distances = pair_distance(slot_name)
    assert len(distances) == PAIR_STATE_COUNT
    assert max(distances) < 255
    reached = sum(1 for value in distances if value != 255)
    assert reached > PAIR_STATE_COUNT // 2


def test_pair_distance_matches_a_solved_pair() -> None:
    solved = CubieCube.solved()
    for name in SLOT_ORDER:
        assert pair_distance(name)[pair_state(solved, SLOTS[name])] == 0


def test_pair_table_contents() -> None:
    table = load_pair_table()
    # Cases whose published algorithm uses rotations are dropped: they would turn
    # the display and break the cross-down convention, so they use the search.
    assert 35 <= len(table.cases) <= 41
    assert all(case.algorithm for case in table.cases.values())
    assert len(table.keys) > 100
    assert load_pair_table() is load_pair_table()


@pytest.mark.parametrize("label", sorted(load_pair_table().cases, key=int))
def test_every_pair_case_inserts_its_pair(label: str) -> None:
    table = load_pair_table()
    case: PairCase = table.cases[label]
    inverse = [move.inverse() for move in reversed(case.moves)]
    state = Cube.solved().apply_moves(inverse)
    result = solve_pair(state, "FR")
    assert two_layers_solved(result.after), case.algorithm


def test_solved_pair_needs_no_moves() -> None:
    result = solve_pair(Cube.solved(), "FR")
    assert result.moves == ()
    assert result.case is None
    assert result.after == Cube.solved()


@pytest.mark.parametrize("index", range(2))
def test_full_f2l_solves_the_first_two_layers(index: int) -> None:
    cube = cross_solved_cubes(2)[index]
    results = solve_f2l(cube)
    assert len(results) == 4
    assert [result.slot for result in results] == list(SLOT_ORDER)
    assert two_layers_solved(results[-1].after)


def test_each_pair_preserves_the_earlier_ones() -> None:
    cube = cross_solved_cubes(1, seed=99)[0]
    current = cube
    done: list[str] = []
    for name in SLOT_ORDER:
        result = solve_pair(current, name, protected=tuple(done))
        cubie = display_cubie(result.after)
        for earlier in [*done, name]:
            assert slot_is_solved(cubie, SLOTS[earlier]), earlier
        current = result.after
        done.append(name)


def test_pair_results_are_serializable() -> None:
    cube = cross_solved_cubes(1, seed=7)[0]
    result = solve_pair(cube, "FR")
    payload = result.to_dict()
    assert payload["slot"] == "FR"
    assert payload["text"] == " ".join(move.name for move in result.moves)
    assert result.length == len(result.moves)
    assert cube.apply_sequence(result.text) == result.after


def test_unknown_slot_is_rejected() -> None:
    with pytest.raises(KeyError):
        solve_pair(Cube.solved(), "XX")

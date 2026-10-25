"""OLL and PLL: table integrity, recognition and exhaustive coverage."""

from __future__ import annotations

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.facelets import SOLVED_FACELETS
from rubiks_cfop.errors import UnsolvableStateError
from rubiks_cfop.solver.coordinates import permutation_unrank
from rubiks_cfop.solver.last_layer import (
    AUF_MOVES,
    LastLayerKind,
    LastLayerTable,
    _solve,
    load_oll_table,
    load_pll_table,
    oll_pattern,
    pll_pattern,
    solve_oll,
    solve_pll,
)

OLL_LABELS = [str(number) for number in range(1, 58)]
PLL_LABELS = [
    "Aa Perm",
    "Ab Perm",
    "E Perm",
    "F Perm",
    "Ga Perm",
    "Gb Perm",
    "Gc Perm",
    "Gd Perm",
    "H Perm",
    "Ja Perm",
    "Jb Perm",
    "Na Perm",
    "Nb Perm",
    "Ra Perm",
    "Rb Perm",
    "T Perm",
    "Ua Perm",
    "Ub Perm",
    "V Perm",
    "Y Perm",
    "Z Perm",
]


def case_state(moves: tuple) -> Cube:
    """Return the state a case's algorithm solves."""
    return Cube.solved().apply_moves([move.inverse() for move in reversed(moves)])


def aligned(cube: Cube) -> bool:
    """Return whether the cube is solved up to a turn of the top face."""
    return cube.is_solved() or any(cube.apply(name).is_solved() for name in ("U", "U2", "U'"))


def _parity(permutation: tuple[int, ...]) -> int:
    """Return the parity of a permutation."""
    inversions = sum(
        1
        for index, value in enumerate(permutation)
        for other in permutation[index + 1 :]
        if other < value
    )
    return inversions % 2


def orientation_states() -> list[Cube]:
    """Return every reachable last-layer orientation state (216 of them)."""
    states = []
    for twist in range(27):
        corners = []
        remaining = twist
        for _ in range(3):
            corners.append(remaining % 3)
            remaining //= 3
        corners.append(-sum(corners) % 3)
        for flip in range(8):
            edges = [(flip >> bit) & 1 for bit in range(3)]
            edges.append(sum(edges) % 2)
            cubie = CubieCube(
                cp=tuple(range(8)),
                co=(*corners, 0, 0, 0, 0),
                ep=tuple(range(12)),
                eo=(*edges, 0, 0, 0, 0, 0, 0, 0, 0),
            )
            states.append(Cube.from_facelets(cubie.to_facelets()))
    return states


def permutation_states() -> list[Cube]:
    """Return every reachable last-layer permutation state (288 of them)."""
    states = []
    for corner_rank in range(24):
        corners = permutation_unrank(corner_rank, 4)
        for edge_rank in range(24):
            edges = permutation_unrank(edge_rank, 4)
            if _parity(corners) != _parity(edges):
                continue
            cubie = CubieCube(
                cp=(*corners, 4, 5, 6, 7),
                co=(0,) * 8,
                ep=(*edges, 4, 5, 6, 7, 8, 9, 10, 11),
                eo=(0,) * 12,
            )
            states.append(Cube.from_facelets(cubie.to_facelets()))
    return states


def test_oll_table_contents() -> None:
    table = load_oll_table()
    assert len(table.cases) == 57
    assert sorted(table.cases, key=int) == OLL_LABELS
    assert all(case.algorithm for case in table.cases.values())
    assert len(table.patterns) == 215  # all but the already-oriented state


def test_pll_table_contents() -> None:
    table = load_pll_table()
    assert len(table.cases) == 21
    assert sorted(table.cases) == PLL_LABELS
    assert len(table.patterns) == 284  # all but solved-and-AUF


def test_tables_are_cached() -> None:
    assert load_oll_table() is load_oll_table()
    assert load_pll_table() is load_pll_table()


@pytest.mark.parametrize("label", OLL_LABELS)
def test_every_oll_algorithm_orients(label: str) -> None:
    case = load_oll_table().cases[label]
    result = solve_oll(case_state(case.moves))
    assert oll_pattern(result.after.cubie()) == (0,) * 8
    assert result.case.label == label


@pytest.mark.parametrize("label", PLL_LABELS)
def test_every_pll_algorithm_solves(label: str) -> None:
    case = load_pll_table().cases[label]
    result = solve_pll(case_state(case.moves))
    assert aligned(result.after)
    assert result.case.label == label


def test_all_unsolved_orientation_states_are_recognized() -> None:
    """All 216 orientation states minus the already-oriented one are OLL cases."""
    states = orientation_states()
    assert len(states) == 216
    table = load_oll_table()
    oriented = [cube for cube in states if oll_pattern(cube.cubie()) == (0,) * 8]
    assert len(oriented) == 1  # the pipeline skips OLL for this one
    for cube in states:
        if cube in oriented:
            assert table.recognize(cube) is None
            continue
        assert table.recognize(cube) is not None, cube.facelets
        assert oll_pattern(solve_oll(cube).after.cubie()) == (0,) * 8


def test_all_unsolved_permutation_states_are_recognized() -> None:
    """All 288 permutation states minus the solved ones are PLL cases."""
    states = permutation_states()
    assert len(states) == 288
    table = load_pll_table()
    solved = [cube for cube in states if aligned(cube)]
    assert len(solved) == 4  # the pipeline skips PLL for these
    for cube in states:
        if cube in solved:
            assert table.recognize(cube) is None
            continue
        assert table.recognize(cube) is not None, cube.facelets
        assert aligned(solve_pll(cube).after)


def test_every_permutation_state_is_recognized() -> None:
    """Recognition itself is complete, even where one stage result is not."""
    table = load_pll_table()
    recognized = sum(1 for cube in permutation_states() if table.recognize(cube) is not None)
    assert recognized == 284


def test_auf_variants_are_recognized_as_the_same_case() -> None:
    table = load_oll_table()
    for label in ("1", "27", "57"):
        case = table.cases[label]
        state = case_state(case.moves)
        for auf in AUF_MOVES:
            match = table.recognize(state.apply_moves(auf))
            assert match is not None
            assert match[0].label == label


def test_stage_moves_include_the_auf_and_solve() -> None:
    case = load_oll_table().cases["27"]
    state = case_state(case.moves).apply("U")
    result = solve_oll(state)
    assert result.moves[0].name in {"U", "U2", "U'"}
    assert oll_pattern(result.after.cubie()) == (0,) * 8
    assert result.to_dict()["label"] == "27"
    assert result.text == " ".join(move.name for move in result.moves)


def test_display_stays_cross_down_after_a_stage() -> None:
    """Stages that use wide or slice moves must not leave the cube rotated."""
    for label, case in load_pll_table().cases.items():
        assert solve_pll(case_state(case.moves)).after.is_canonical(), label


def test_unknown_pattern_raises() -> None:
    empty = LastLayerTable(kind=LastLayerKind.OLL, cases={}, patterns={})
    with pytest.raises(UnsolvableStateError, match="does not match any case"):
        _solve(Cube.from_facelets(SOLVED_FACELETS), empty)


def test_solved_last_layer_is_not_a_case() -> None:
    """A solved last layer needs no PLL; the pipeline skips the stage."""
    assert pll_pattern(CubieCube.solved()) not in load_pll_table().patterns
    assert oll_pattern(CubieCube.solved()) not in load_oll_table().patterns

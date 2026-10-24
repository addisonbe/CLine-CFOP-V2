"""The CFOP pipeline: stage order, output labels and verified solutions."""

from __future__ import annotations

import json
import random

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import FACE_COLOR, Color, Face
from rubiks_cfop.cube.moves import MOVES
from rubiks_cfop.solver.cfop import cross_options, solve_cube

FACE_MOVES = [name for name in MOVES if MOVES[name].kind == "face"]
STAGE_LABELS = ("Cross", "F2L1", "F2L2", "F2L3", "F2L4")


@pytest.fixture(scope="module")
def solved() -> list:
    """Two solved cubes, generated once: a full solve takes a while."""
    rng = random.Random(2026)
    results = []
    for _ in range(2):
        cube = Cube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
        results.append((cube, solve_cube(cube)))
    return results


def test_stage_order_and_labels(solved: list) -> None:
    for _cube, solution in solved:
        labels = [stage.label for stage in solution.stages]
        assert tuple(labels[:5]) == STAGE_LABELS
        assert labels[5].startswith("OLL (")
        assert labels[6].startswith("PLL (")
        assert len(solution.stages) >= 7


def test_oll_number_is_in_range(solved: list) -> None:
    for _, solution in solved:
        oll = solution.stages[5]
        if oll.metadata["number"] is None:
            assert oll.label == "OLL (skip)"
        else:
            assert 1 <= int(oll.metadata["number"]) <= 57  # type: ignore[arg-type]
            assert oll.label == f"OLL ({oll.metadata['number']})"


def test_pll_name_is_a_standard_case(solved: list) -> None:
    names = {
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
    }
    for _, solution in solved:
        pll = solution.stages[6]
        if pll.metadata["case"] is None:
            assert pll.label == "PLL (skip)"
        else:
            assert pll.metadata["case"] in names
            assert pll.label == f"PLL ({pll.metadata['case']})"


def test_solution_is_verified_and_solves_the_cube(solved: list) -> None:
    for cube, solution in solved:
        assert solution.verified
        assert solution.final.is_solved()
        assert cube.apply_moves(solution.moves).is_solved()
        assert solution.total_moves == sum(stage.length for stage in solution.stages)


def test_cross_is_in_the_bottom_layer(solved: list) -> None:
    for _, solution in solved:
        cross = solution.stages[0]
        bottom = Face(cross.after.face_facelets(Face.D)[4])
        top = Face(cross.after.face_facelets(Face.U)[4])
        assert FACE_COLOR[bottom] is solution.cross_color
        assert FACE_COLOR[top] is not solution.cross_color


def test_payload_is_json_ready(solved: list) -> None:
    _, solution = solved[0]
    payload = json.loads(json.dumps(solution.to_dict()))
    assert payload["verified"] is True
    assert payload["cross_color"] in {color.value for color in Color}
    assert len(payload["stages"]) >= 7
    assert all("moves" in stage and "label" in stage for stage in payload["stages"])


def test_cross_options_are_ranked() -> None:
    rng = random.Random(5)
    cube = Cube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    options = cross_options(cube)
    assert len(options) == 6
    lengths = [option.length for option in options]
    assert lengths == sorted(lengths)
    assert options[0].length == min(lengths)


def test_explicit_cross_colour() -> None:
    rng = random.Random(6)
    cube = Cube.solved().apply_moves([rng.choice(FACE_MOVES) for _ in range(25)])
    solution = solve_cube(cube, cross=Color.YELLOW)
    assert solution.cross_color is Color.YELLOW
    assert solution.verified


def test_solved_cube_needs_no_turning_moves() -> None:
    """A solved cube may be reoriented (white cross down), but nothing is turned."""
    solution = solve_cube(Cube.solved())
    assert solution.verified
    assert all(move.kind == "rotation" for move in solution.moves)
    assert solution.stages[0].metadata["color"] == Color.WHITE.value
    assert all(stage.length == 0 for stage in solution.stages[1:5])
    assert solution.stages[5].label == "OLL (skip)"
    assert solution.stages[6].label == "PLL (skip)"

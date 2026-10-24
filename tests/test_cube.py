"""The immutable ``Cube`` value object."""

from __future__ import annotations

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import SOLVED_FACELETS, Color, Face
from rubiks_cfop.cube.moves import MOVES
from rubiks_cfop.errors import InvalidMoveError, InvalidStateError, NotationError


def test_solved_cube() -> None:
    cube = Cube.solved()
    assert cube.facelets == SOLVED_FACELETS
    assert str(cube) == SOLVED_FACELETS
    assert cube.is_solved()
    assert cube.is_canonical()
    assert cube.is_solvable()


def test_construction_normalises_whitespace_and_case() -> None:
    cube = Cube("  uuuuuuuuu rrrrrrrrr fffffffff ddddddddd lllllllll bbbbbbbbb ")
    assert cube == Cube.solved()


def test_construction_validates() -> None:
    with pytest.raises(InvalidStateError):
        Cube("U" * 54)


def test_apply_returns_a_new_cube() -> None:
    start = Cube.solved()
    after = start.apply("R")
    assert start.facelets == SOLVED_FACELETS
    assert after != start
    assert after.facelets == MOVES["R"].apply_to(SOLVED_FACELETS)


def test_apply_accepts_move_objects_and_names() -> None:
    assert Cube.solved().apply(MOVES["R"]) == Cube.solved().apply("R")
    assert Cube.solved().apply("R'") == Cube.solved().apply("R").apply("R2")


def test_apply_rejects_unknown_names() -> None:
    with pytest.raises(InvalidMoveError):
        Cube.solved().apply("Rw3")


def test_apply_moves_and_sequences_agree() -> None:
    sequence = ("R", "U", "R'", "U'", "F2", "Rw", "M'", "x")
    by_moves = Cube.solved().apply_moves(sequence)
    by_fold = Cube.solved()
    for name in sequence:
        by_fold = by_fold.apply(name)
    assert by_moves == by_fold
    assert Cube.solved().apply_sequence(" ".join(sequence)) == by_moves


def test_apply_scramble_matches_apply_sequence() -> None:
    scramble = "R U R' U' F2 D L2 B' Rw U2 M' x y' z2"
    assert Cube.solved().apply_scramble(scramble) == Cube.solved().apply_sequence(scramble)


def test_apply_sequence_rejects_bad_notation() -> None:
    with pytest.raises(NotationError):
        Cube.solved().apply_sequence("R Q")


def test_inverse_sequence_restores_the_cube() -> None:
    scramble = "R U R' U' F2 D L2 B'"
    scrambled = Cube.solved().apply_sequence(scramble)
    restored = scrambled.apply_sequence("B L2 D' F2 U R U' R'")
    assert restored.is_solved()


def test_rotated_cube_counts_as_solved() -> None:
    rotated = Cube.solved().apply_sequence("x y' z2")
    assert rotated.is_solved()
    assert not rotated.is_canonical()
    assert rotated.normalized() == Cube.solved()


def test_normalized_is_idempotent() -> None:
    scrambled = Cube.solved().apply_sequence("R U F' y2")
    once = scrambled.normalized()
    assert once.is_canonical()
    assert once.normalized() == once


def test_facelet_and_face_accessors() -> None:
    cube = Cube.solved().apply("R")
    assert cube.facelet("U1") == cube.facelets[0]
    assert cube.face_facelets(Face.U) == cube.facelets[0:9]
    assert cube.face_facelets("R") == cube.facelets[9:18]


def test_colors_follow_the_scheme() -> None:
    colors = Cube.solved().colors()
    assert len(colors) == 54
    assert colors[0] is Color.WHITE
    assert colors[9] is Color.RED
    assert colors[18] is Color.GREEN
    assert colors[27] is Color.YELLOW
    assert colors[36] is Color.ORANGE
    assert colors[45] is Color.BLUE


def test_to_dict_round_trip() -> None:
    cube = Cube.solved().apply_sequence("R U R'")
    payload = cube.to_dict()
    assert payload == {"facelets": cube.facelets}
    assert Cube.from_dict(payload) == cube


def test_cubes_are_hashable_and_comparable() -> None:
    first = Cube.solved().apply("R")
    second = Cube.solved().apply("R")
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_cubie_view_is_available() -> None:
    assert Cube.solved().cubie().is_solved()
    assert Cube.solved().apply("R").cubie().is_solvable()


def test_from_facelets_classmethod() -> None:
    assert Cube.from_facelets(SOLVED_FACELETS) == Cube.solved()
    assert Cube.from_facelets(f"  {SOLVED_FACELETS.lower()} ") == Cube.solved()
    with pytest.raises(InvalidStateError):
        Cube.from_facelets("U" * 54)


def test_unsolvable_state_is_detected() -> None:
    """Swapping two stickers of one corner twists it, which no cube allows."""
    facelets = list(SOLVED_FACELETS)
    facelets[8], facelets[9] = facelets[9], facelets[8]
    broken = Cube("".join(facelets))
    assert broken.facelets != SOLVED_FACELETS
    assert not broken.is_solvable()

"""Move tables: identities, geometry and Kociemba's published definitions."""

from __future__ import annotations

import pytest
from tests._kociemba_reference import KOCIEMBA_FACE_MOVES

from rubiks_cfop.cube.facelets import (
    FACE_ORDER,
    FACELET_COUNT,
    SOLVED_FACELETS,
    Face,
    face_facelets,
)
from rubiks_cfop.cube.moves import (
    BASE_MOVE_NAMES,
    MOVE_NAMES,
    MOVES,
    MoveKind,
    compose,
    conjugate,
    get_move,
    invert,
    invert_permutation,
    move_names,
    normalized_facelets,
    rotation_to_normalize,
    rotations,
)
from rubiks_cfop.errors import InvalidMoveError, InvalidStateError

FACE_MOVE_NAMES = [
    f"{base}{suffix}" for base in ("U", "R", "F", "D", "L", "B") for suffix in ("", "2", "'")
]
WIDE_MOVE_NAMES = [
    f"{base}{suffix}" for base in ("Uw", "Rw", "Fw", "Dw", "Lw", "Bw") for suffix in ("", "2", "'")
]
ROTATION_MOVE_NAMES = [f"{base}{suffix}" for base in ("x", "y", "z") for suffix in ("", "2", "'")]
SLICE_MOVE_NAMES = [f"{base}{suffix}" for base in ("M", "E", "S") for suffix in ("", "2", "'")]


def apply(sequence: tuple[str, ...], facelets: str = SOLVED_FACELETS) -> str:
    """Apply move names to a facelet string."""
    state = facelets
    for name in sequence:
        state = MOVES[name].apply_to(state)
    return state


def test_move_table_shape() -> None:
    assert len(MOVE_NAMES) == 54
    assert len(BASE_MOVE_NAMES) == 18
    assert move_names() == MOVE_NAMES
    assert sorted(MOVES) == sorted(MOVE_NAMES)


@pytest.mark.parametrize("name", sorted(MOVE_NAMES))
def test_permutations_are_bijections(name: str) -> None:
    move = MOVES[name]
    assert len(move.carried_to) == FACELET_COUNT
    assert sorted(move.carried_to) == list(range(FACELET_COUNT))
    assert invert_permutation(move.carried_to) == move.replaced_by


@pytest.mark.parametrize("name", sorted(MOVE_NAMES))
def test_move_and_its_inverse_cancel(name: str) -> None:
    move = MOVES[name]
    inverse = invert(move)
    assert inverse.inverse() == move
    assert apply((move.name, inverse.name)) == SOLVED_FACELETS


@pytest.mark.parametrize("name", sorted(MOVE_NAMES))
def test_quarter_turn_order_is_four(name: str) -> None:
    move = MOVES[name]
    repeats = 2 if move.turns == 2 else 4
    assert apply(tuple([name] * repeats)) == SOLVED_FACELETS


@pytest.mark.parametrize("base", BASE_MOVE_NAMES)
def test_double_and_inverse_are_compositions(base: str) -> None:
    quarter = MOVES[base]
    double = MOVES[f"{base}2"]
    assert double.carried_to == compose(quarter.carried_to, quarter.carried_to)
    assert MOVES[f"{base}'"].carried_to == compose(double.carried_to, quarter.carried_to)


@pytest.mark.parametrize("name", sorted(KOCIEMBA_FACE_MOVES))
def test_face_moves_match_kociemba(name: str) -> None:
    assert MOVES[name].carried_to == KOCIEMBA_FACE_MOVES[name]


def test_face_move_kinds_and_faces() -> None:
    for name in FACE_MOVE_NAMES:
        move = get_move(name)
        assert move.kind is MoveKind.FACE
        assert move.face is not None
        assert move.name[0] == move.face.value
    for name in WIDE_MOVE_NAMES:
        move = get_move(name)
        assert move.kind is MoveKind.WIDE
        assert move.face is not None
    for name in SLICE_MOVE_NAMES:
        move = get_move(name)
        assert move.kind is MoveKind.SLICE
        assert move.face is None
    for name in ROTATION_MOVE_NAMES:
        move = get_move(name)
        assert move.kind is MoveKind.ROTATION
        assert move.face is None


def test_unknown_move_is_rejected() -> None:
    with pytest.raises(InvalidMoveError, match="unknown move"):
        get_move("Rw3")


def test_apply_to_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="54 facelets"):
        get_move("R").apply_to("UUU")


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def test_slice_moves_rotate_the_middle_layer_only() -> None:
    # M follows L, so the top center receives the back color and R/L are untouched.
    assert face_facelets(apply(("M",)), Face.U)[4] == "B"
    assert face_facelets(apply(("M",)), Face.R)[4] == "R"
    assert face_facelets(apply(("M",)), Face.L)[4] == "L"
    # E follows D, so the front center receives the left color and U/D are untouched.
    assert face_facelets(apply(("E",)), Face.F)[4] == "L"
    assert face_facelets(apply(("E",)), Face.U)[4] == "U"
    assert face_facelets(apply(("E",)), Face.D)[4] == "D"
    # S follows F, so the top center receives the left color and F/B are untouched.
    assert face_facelets(apply(("S",)), Face.U)[4] == "L"
    assert face_facelets(apply(("S",)), Face.F)[4] == "F"
    assert face_facelets(apply(("S",)), Face.B)[4] == "B"


def test_wide_move_identities_against_face_and_slice_moves() -> None:
    identities = {
        "Rw": ("R", "M'"),
        "Lw": ("L", "M"),
        "Uw": ("U", "E'"),
        "Dw": ("D", "E"),
        "Fw": ("F", "S"),
        "Bw": ("B", "S'"),
    }
    for wide, parts in identities.items():
        assert apply((wide,)) == apply(parts), wide


def test_rotation_identities_against_face_and_slice_moves() -> None:
    identities = {"x": ("R", "M'", "L'"), "y": ("U", "E'", "D'"), "z": ("F", "S", "B'")}
    for rotation, parts in identities.items():
        assert apply((rotation,)) == apply(parts), rotation


def test_rotations_are_exactly_twenty_four() -> None:
    found = rotations()
    assert len(found) == 24
    assert len({apply(sequence) for sequence in found}) == 24
    assert SOLVED_FACELETS in {apply(sequence) for sequence in found}


def test_rotations_keep_faces_uniform() -> None:
    for sequence in rotations():
        state = apply(sequence)
        for face in FACE_ORDER:
            assert len(set(face_facelets(state, face))) == 1


def test_rotation_face_mapping() -> None:
    """After a rotation, a face shows the color that was on the rotated-away face."""
    expected = {
        "x": {"U": "F", "F": "D", "D": "B", "B": "U", "R": "R", "L": "L"},
        "y": {"F": "R", "R": "B", "B": "L", "L": "F", "U": "U", "D": "D"},
        "z": {"U": "L", "L": "D", "D": "R", "R": "U", "F": "F", "B": "B"},
    }
    for rotation, mapping in expected.items():
        state = apply((rotation,))
        for face, letter in mapping.items():
            assert face_facelets(state, face)[4] == letter, (rotation, face)


def test_normalization_undoes_rotations() -> None:
    scrambled = apply(("R", "U", "R'", "U'", "F2"))
    for sequence in rotations():
        assert normalized_facelets(apply(sequence, scrambled)) == scrambled


def test_rotation_to_normalize_is_empty_for_canonical_states() -> None:
    assert rotation_to_normalize(apply(("R", "U"))) == ()
    assert rotation_to_normalize(apply(("R", "U", "y", "y'"))) == ()


def test_rotation_to_normalize_rejects_impossible_centers() -> None:
    """Centers that are not a rotation of the solved arrangement cannot occur."""
    facelets = list(SOLVED_FACELETS)
    facelets[4], facelets[31] = facelets[31], facelets[4]  # swap the U and D centers
    with pytest.raises(InvalidStateError, match="not a rotation"):
        rotation_to_normalize("".join(facelets))


@pytest.mark.parametrize("name", sorted(FACE_MOVE_NAMES))
def test_conjugation_matches_the_display(name: str) -> None:
    """``conjugate(m, r)`` must describe the physical turn ``r m r'``."""
    for rotation in ("x", "y", "z", "x2", "y'", "z2"):
        conjugated = conjugate(MOVES[name].carried_to, MOVES[rotation].carried_to)
        displayed = apply((rotation, name, invert(get_move(rotation)).name))
        expected = "".join(SOLVED_FACELETS[index] for index in invert_permutation(conjugated))
        assert displayed == expected, (name, rotation)

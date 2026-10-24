"""Facelet indexing, colour scheme and validation."""

from __future__ import annotations

import pytest

from rubiks_cfop.cube.facelets import (
    COLOR_FACE,
    FACE_COLOR,
    FACE_ORDER,
    FACELET_COUNT,
    FACELETS_PER_FACE,
    SOLVED_FACELETS,
    Color,
    Face,
    centers_are_canonical,
    face_facelets,
    face_index,
    face_of,
    facelet,
    facelet_index,
    facelet_name,
    facelets_of_face,
    index_of_name,
    is_solved_facelets,
    normalize_facelets,
    validate_facelets,
)
from rubiks_cfop.errors import InvalidStateError


def test_solved_facelets_constant() -> None:
    assert SOLVED_FACELETS == "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
    assert len(SOLVED_FACELETS) == FACELET_COUNT == 54


def test_face_order_is_kociemba_order() -> None:
    assert tuple(face.value for face in FACE_ORDER) == ("U", "R", "F", "D", "L", "B")
    assert [face_index(face) for face in FACE_ORDER] == [0, 1, 2, 3, 4, 5]
    assert face_index("F") == 2


def test_facelet_index_and_name_round_trip() -> None:
    for index in range(FACELET_COUNT):
        name = facelet_name(index)
        assert index_of_name(name) == index
        assert face_of(index) is Face(name[0])


def test_facelet_index_matches_kociemba_numbering() -> None:
    assert facelet_index(Face.U, 1) == 0
    assert facelet_index(Face.R, 1) == 9
    assert facelet_index(Face.F, 3) == 20
    assert facelet_index(Face.D, 9) == 35
    assert facelet_index(Face.L, 1) == 36
    assert facelet_index(Face.B, 9) == 53


def test_facelets_of_face_are_contiguous() -> None:
    for position, face in enumerate(FACE_ORDER):
        indices = facelets_of_face(face)
        assert len(indices) == FACELETS_PER_FACE
        assert indices == tuple(range(position * 9, position * 9 + 9))


@pytest.mark.parametrize("position", [0, 10, -1])
def test_facelet_index_rejects_bad_position(position: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 9"):
        facelet_index(Face.U, position)


@pytest.mark.parametrize("index", [-1, 54, 100])
def test_facelet_name_rejects_bad_index(index: int) -> None:
    with pytest.raises(ValueError, match="between 0 and 53"):
        facelet_name(index)


@pytest.mark.parametrize("index", [-1, 54])
def test_face_of_rejects_bad_index(index: int) -> None:
    with pytest.raises(ValueError, match="between 0 and 53"):
        face_of(index)


@pytest.mark.parametrize("name", ["", "U", "U10", "X1", "UU", "1U"])
def test_index_of_name_rejects_bad_names(name: str) -> None:
    with pytest.raises(ValueError, match="not a facelet name"):
        index_of_name(name)


def test_index_of_name_tolerates_case_and_space() -> None:
    assert index_of_name(" u1 ") == 0
    assert index_of_name("b9") == 53


def test_colour_scheme_is_the_wca_scheme() -> None:
    assert FACE_COLOR[Face.U] is Color.WHITE
    assert FACE_COLOR[Face.R] is Color.RED
    assert FACE_COLOR[Face.F] is Color.GREEN
    assert FACE_COLOR[Face.D] is Color.YELLOW
    assert FACE_COLOR[Face.L] is Color.ORANGE
    assert FACE_COLOR[Face.B] is Color.BLUE
    assert all(COLOR_FACE[color] is face for face, color in FACE_COLOR.items())


def test_normalize_facelets() -> None:
    assert normalize_facelets("  uu rr\nff  ") == "UUR RFF".replace(" ", "")


def test_validate_facelets_accepts_solved_and_rotated() -> None:
    assert validate_facelets(SOLVED_FACELETS) == SOLVED_FACELETS
    assert validate_facelets(SOLVED_FACELETS.lower()) == SOLVED_FACELETS
    # Swapping the U and D blocks is a valid state (a rotated cube).
    rotated = (
        SOLVED_FACELETS[27:36] + SOLVED_FACELETS[9:27] + SOLVED_FACELETS[0:9] + SOLVED_FACELETS[36:]
    )
    assert validate_facelets(rotated) == rotated


def test_validate_facelets_rejects_wrong_length() -> None:
    with pytest.raises(InvalidStateError) as error:
        validate_facelets("U" * 53)
    assert error.value.to_dict()["details"] == {"length": 53}


def test_validate_facelets_rejects_unknown_letters() -> None:
    with pytest.raises(InvalidStateError) as error:
        validate_facelets("X" + SOLVED_FACELETS[1:])
    assert error.value.to_dict()["details"] == {"letters": ["X"]}


def test_validate_facelets_rejects_wrong_counts() -> None:
    broken = "U" * 10 + SOLVED_FACELETS[10:]
    with pytest.raises(InvalidStateError) as error:
        validate_facelets(broken)
    assert error.value.to_dict()["details"] == {"counts": {"U": 10, "R": 8}}


def test_centers_are_canonical() -> None:
    assert centers_are_canonical(SOLVED_FACELETS)
    rotated = "D" * 9 + "U" * 9 + SOLVED_FACELETS[18:]
    assert not centers_are_canonical(rotated)


def test_is_solved_facelets() -> None:
    assert is_solved_facelets(SOLVED_FACELETS)
    assert is_solved_facelets(SOLVED_FACELETS.lower())
    assert not is_solved_facelets(SOLVED_FACELETS[:-1] + "U")


def test_facelet_and_face_facelets() -> None:
    assert facelet(SOLVED_FACELETS, "U1") == "U"
    assert facelet(SOLVED_FACELETS, "B9") == "B"
    assert face_facelets(SOLVED_FACELETS, Face.L) == "LLLLLLLLL"
    assert face_facelets(SOLVED_FACELETS, "D") == "DDDDDDDDD"

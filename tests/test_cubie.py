"""The cubie level projection and the cube's algebraic invariants."""

from __future__ import annotations

import math
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rubiks_cfop.cube.cubie import (
    CORNER_NAMES,
    EDGE_NAMES,
    CubieCube,
    corner_position,
    edge_position,
    move_cubie,
)
from rubiks_cfop.cube.facelets import SOLVED_FACELETS
from rubiks_cfop.cube.moves import MOVE_NAMES, MOVES, normalized_facelets
from rubiks_cfop.errors import InvalidMoveError, InvalidStateError, UnsolvableStateError

FACE_MOVES = tuple(name for name in MOVE_NAMES if MOVES[name].kind == "face")
ROTATIONS = tuple(name for name in MOVE_NAMES if MOVES[name].kind == "rotation")

#: The order of the cube group: 8! corner arrangements times 3^7 twists, times
#: 12! edge arrangements times 2^11 flips, with the parity constraint halving it.
CUBE_GROUP_ORDER = math.factorial(8) * 3**7 * math.factorial(12) * 2**11 // 2


def scramble(names: tuple[str, ...], rng: random.Random, length: int = 20) -> str:
    """Return a random move sequence from ``names``."""
    return " ".join(rng.choice(names) for _ in range(length))


def facelets_after(text: str) -> str:
    """Apply a move sequence to the solved cube and return the facelets."""
    state = SOLVED_FACELETS
    for name in text.split():
        state = MOVES[name].apply_to(state)
    return state


def test_solved_cubie_state() -> None:
    solved = CubieCube.solved()
    assert solved.cp == tuple(range(8))
    assert solved.co == (0,) * 8
    assert solved.ep == tuple(range(12))
    assert solved.eo == (0,) * 12
    assert solved.is_solved()
    assert solved.is_solvable()


def test_facelets_and_cubies_round_trip() -> None:
    rng = random.Random(2026)
    for _ in range(50):
        facelets = facelets_after(scramble(FACE_MOVES, rng))
        cubie = CubieCube.from_facelets(facelets)
        assert cubie.to_facelets() == facelets


def test_rotations_do_not_change_the_cubie_state() -> None:
    rng = random.Random(7)
    for _ in range(50):
        facelets = facelets_after(scramble(FACE_MOVES, rng))
        reference = CubieCube.from_facelets(facelets)
        for rotation in ROTATIONS:
            rotated = MOVES[rotation].apply_to(facelets)
            assert CubieCube.from_facelets(rotated) == reference
            assert CubieCube.from_facelets(rotated).to_facelets() == normalized_facelets(rotated)


def test_random_states_are_solvable() -> None:
    rng = random.Random(99)
    for _ in range(100):
        cubie = CubieCube.from_facelets(facelets_after(scramble(FACE_MOVES, rng)))
        assert cubie.is_solvable()
        cubie.validate()


def test_twisted_corner_is_rejected() -> None:
    twisted = CubieCube(
        cp=tuple(range(8)), co=(1, 0, 0, 0, 0, 0, 0, 0), ep=tuple(range(12)), eo=(0,) * 12
    )
    with pytest.raises(UnsolvableStateError, match="corner orientation"):
        twisted.validate()
    assert not twisted.is_solvable()


def test_flipped_edge_is_rejected() -> None:
    flipped = CubieCube(cp=tuple(range(8)), co=(0,) * 8, ep=tuple(range(12)), eo=(1,) + (0,) * 11)
    with pytest.raises(UnsolvableStateError, match="edge orientation"):
        flipped.validate()


def test_parity_mismatch_is_rejected() -> None:
    swapped = CubieCube(cp=(1, 0, 2, 3, 4, 5, 6, 7), co=(0,) * 8, ep=tuple(range(12)), eo=(0,) * 12)
    with pytest.raises(UnsolvableStateError, match="parity"):
        swapped.validate()


def test_malformed_permutations_are_rejected() -> None:
    with pytest.raises(InvalidStateError, match="corner permutation"):
        CubieCube(cp=(0,) * 8, co=(0,) * 8, ep=tuple(range(12)), eo=(0,) * 12).validate()
    with pytest.raises(InvalidStateError, match="edge permutation"):
        CubieCube(cp=tuple(range(8)), co=(0,) * 8, ep=(0,) * 12, eo=(0,) * 12).validate()
    with pytest.raises(InvalidStateError, match="corner orientations"):
        CubieCube(
            cp=tuple(range(8)), co=(3,) + (0,) * 7, ep=tuple(range(12)), eo=(0,) * 12
        ).validate()
    with pytest.raises(InvalidStateError, match="edge orientations"):
        CubieCube(
            cp=tuple(range(8)), co=(0,) * 8, ep=tuple(range(12)), eo=(2,) + (0,) * 11
        ).validate()


def test_unknown_pieces_are_rejected() -> None:
    broken = "R" + SOLVED_FACELETS[1:]
    with pytest.raises(InvalidStateError, match=r"no up or down sticker|unknown corner piece"):
        CubieCube.from_facelets(broken)


def test_impossible_corner_piece_is_rejected() -> None:
    """Swapping two side stickers creates a corner color triple that cannot exist."""
    facelets = list(SOLVED_FACELETS)
    facelets[20], facelets[11] = facelets[11], facelets[20]  # F3 (URF) and R3 (UBR)
    with pytest.raises(InvalidStateError, match="unknown corner piece"):
        CubieCube.from_facelets("".join(facelets))


def test_impossible_edge_piece_is_rejected() -> None:
    """Swapping an up sticker with a side sticker creates two identical edge colors."""
    facelets = list(SOLVED_FACELETS)
    facelets[7], facelets[10] = facelets[10], facelets[7]  # U8 (UF) and R2 (UR)
    with pytest.raises(InvalidStateError, match="unknown edge piece"):
        CubieCube.from_facelets("".join(facelets))


def test_move_cubie_matches_the_display() -> None:
    for name in ("R", "U2", "F'"):
        assert move_cubie(MOVES[name]) == CubieCube.from_facelets(
            MOVES[name].apply_to(SOLVED_FACELETS)
        )


def test_apply_face_moves_and_rotations() -> None:
    assert CubieCube.solved().apply("R") == CubieCube.from_facelets(
        MOVES["R"].apply_to(SOLVED_FACELETS)
    )
    assert CubieCube.solved().apply("y") == CubieCube.solved()
    assert CubieCube.solved().apply_moves(["x", "y2", "z'"]) == CubieCube.solved()


def test_wide_and_slice_moves_are_rejected() -> None:
    for name in ("Rw", "Uw'", "M", "E2", "S'"):
        with pytest.raises(InvalidMoveError, match="not cubie group elements"):
            CubieCube.solved().apply(name)
        with pytest.raises(InvalidMoveError, match="not cubie group elements"):
            CubieCube.solved().apply_moves([name])


def test_rotation_frame_is_tracked() -> None:
    """``y R y'`` is the physical turn of the face that ``y`` moved to R."""
    assert CubieCube.solved().apply_moves(["y", "R", "y'"]) == CubieCube.solved().apply("B")
    assert CubieCube.solved().apply_moves(["x", "U", "x'"]) == CubieCube.solved().apply("F")
    assert CubieCube.solved().apply_moves(["z", "R", "z'"]) == CubieCube.solved().apply("U")


def test_position_helpers() -> None:
    for index, name in enumerate(CORNER_NAMES):
        assert corner_position(name) == index
        assert corner_position(name.lower()) == index
    for index, name in enumerate(EDGE_NAMES):
        assert edge_position(name) == index
    with pytest.raises(ValueError, match="not a corner position"):
        corner_position("XYZ")
    with pytest.raises(ValueError, match="not an edge position"):
        edge_position("XYZ")


def test_state_space_size_matches_the_cube_group_order() -> None:
    """The model has exactly the degrees of freedom a real cube has."""
    assert CUBE_GROUP_ORDER == 43252003274489856000


@given(st.lists(st.sampled_from(FACE_MOVES), min_size=1, max_size=12))
def test_hypothesis_sequences_stay_valid(names: list[str]) -> None:
    cubie = CubieCube.solved().apply_moves(names)
    cubie.validate()
    assert CubieCube.from_facelets(cubie.to_facelets()) == cubie

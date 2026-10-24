"""The random-move scramble generator."""

from __future__ import annotations

import itertools
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import FACE_ORDER, Face
from rubiks_cfop.scramble import (
    Scramble,
    ScrambleStyle,
    generate_scramble,
    generate_scrambles,
    random_move_scramble,
    random_move_scrambles,
)
from rubiks_cfop.scramble.random_move import DEFAULT_LENGTH, FACE_TURNS, _axis_of

SCRAMBLE_RE = re.compile(r"^[URFDLB](2|')?( [URFDLB](2|')?)*$")


def faces_of(scramble: Scramble) -> list[Face]:
    """Return the face of each move in a scramble."""
    return [move.face for move in scramble.moves if move.face is not None]


def test_default_length() -> None:
    assert random_move_scramble(seed=1).length == DEFAULT_LENGTH == 20


def test_custom_length() -> None:
    assert random_move_scramble(seed=1, length=25).length == 25
    assert random_move_scramble(seed=1, length=1).length == 1


@pytest.mark.parametrize("length", [0, -1])
def test_length_must_be_positive(length: int) -> None:
    with pytest.raises(ValueError, match="length must be positive"):
        random_move_scramble(seed=1, length=length)


def test_text_is_wca_notation() -> None:
    for seed in range(20):
        scramble = random_move_scramble(seed=seed)
        assert SCRAMBLE_RE.fullmatch(scramble.text)
        assert str(scramble) == scramble.text


def test_only_face_turns_are_used() -> None:
    for seed in range(20):
        assert all(move.name in FACE_TURNS for move in random_move_scramble(seed=seed).moves)


def test_no_consecutive_same_face() -> None:
    for seed in range(50):
        faces = faces_of(random_move_scramble(seed=seed))
        assert all(first is not second for first, second in itertools.pairwise(faces))


def test_no_three_turns_on_one_axis() -> None:
    for seed in range(50):
        faces = faces_of(random_move_scramble(seed=seed))
        for first, second, third in zip(faces, faces[1:], faces[2:], strict=False):
            assert len({_axis_of(first), _axis_of(second), _axis_of(third)}) > 1


def test_axes_are_well_defined() -> None:
    assert {_axis_of(face) for face in FACE_ORDER} == {0, 1, 2}
    assert _axis_of(Face.R) == _axis_of(Face.L)
    assert _axis_of(Face.U) == _axis_of(Face.D)
    assert _axis_of(Face.F) == _axis_of(Face.B)


def test_state_matches_the_moves() -> None:
    for seed in range(10):
        scramble = random_move_scramble(seed=seed)
        assert scramble.state == Cube.solved().apply_moves(scramble.moves)


def test_scramble_is_not_solved_and_the_inverse_solves_it() -> None:
    for seed in range(20):
        scramble = random_move_scramble(seed=seed)
        assert not scramble.state.is_solved()
        inverse = [move.inverse() for move in reversed(scramble.moves)]
        assert scramble.state.apply_moves(inverse).is_solved()


def test_determinism() -> None:
    first = random_move_scramble(seed=12345)
    second = random_move_scramble(seed=12345)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_different_seeds_give_different_scrambles() -> None:
    assert len({random_move_scramble(seed=seed).text for seed in range(50)}) >= 45


def test_seed_is_recorded_when_generated() -> None:
    scramble = random_move_scramble()
    assert isinstance(scramble.seed, int)
    assert random_move_scramble(seed=scramble.seed) == scramble


def test_style_is_recorded() -> None:
    assert random_move_scramble(seed=1).style is ScrambleStyle.RANDOM_MOVE


def test_to_dict_round_trip() -> None:
    scramble = random_move_scramble(seed=99)
    payload = scramble.to_dict()
    assert payload["style"] == "random-move"
    assert payload["seed"] == 99
    assert payload["moves"] == [move.name for move in scramble.moves]
    assert Scramble.from_dict(payload) == scramble


def test_generate_scramble_dispatches() -> None:
    assert generate_scramble(seed=1, style="random-move") == random_move_scramble(seed=1)
    assert generate_scramble(seed=1, style=ScrambleStyle.RANDOM_MOVE) == random_move_scramble(
        seed=1
    )


def test_generate_scramble_rejects_unknown_style() -> None:
    with pytest.raises(ValueError, match="not a valid ScrambleStyle"):
        generate_scramble(style="random-turn")


def test_random_state_style_is_dispatched_elsewhere() -> None:
    """The random-state generator has its own module and test file."""
    assert generate_scramble(seed=3, style="random-state").style.value == "random-state"


def test_generate_scrambles_are_independent() -> None:
    scrambles = generate_scrambles(10, seed=4242)
    assert len(scrambles) == 10
    assert len({scramble.text for scramble in scrambles}) == 10
    assert scrambles == generate_scrambles(10, seed=4242)


def test_generate_scrambles_validates_count() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        generate_scrambles(-1)
    with pytest.raises(ValueError, match="must not be negative"):
        random_move_scrambles(-1)


def test_generate_scrambles_empty() -> None:
    assert generate_scrambles(0) == []


def test_generate_scrambles_without_a_seed_still_works() -> None:
    scrambles = generate_scrambles(3, style="random-move")
    assert len(scrambles) == 3
    assert len({scramble.seed for scramble in scrambles}) == 3


def test_generate_scrambles_accepts_random_state() -> None:
    assert len(generate_scrambles(1, seed=4, style="random-state")) == 1


def test_scramble_from_moves_derives_the_state() -> None:
    scramble = random_move_scramble(seed=7)
    rebuilt = Scramble.from_moves(
        scramble.moves, style=ScrambleStyle.RANDOM_MOVE, seed=scramble.seed
    )
    assert rebuilt == scramble


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_hypothesis_scrambles_are_well_formed(seed: int) -> None:
    scramble = random_move_scramble(seed=seed)
    assert scramble.length == DEFAULT_LENGTH
    assert SCRAMBLE_RE.fullmatch(scramble.text)
    assert scramble.state == Cube.solved().apply_moves(scramble.moves)
    faces = faces_of(scramble)
    assert all(first is not second for first, second in itertools.pairwise(faces))

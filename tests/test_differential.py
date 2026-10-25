"""Differential tests: the facelet model against the cubie model.

The two models are written independently -- one permutes 54 stickers, the other
permutes 20 cubies with orientations -- so agreement between them after thousands
of random sequences is strong evidence that both are right.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.moves import MOVE_NAMES, MOVES, normalized_facelets
from rubiks_cfop.cube.notation import parse_moves

FACE_MOVES = [name for name in MOVE_NAMES if MOVES[name].kind == "face"]
ROTATIONS = [name for name in MOVE_NAMES if MOVES[name].kind == "rotation"]
ALL_MOVES = list(MOVE_NAMES)

#: Known algorithm orders, checked end to end: (algorithm, repetitions to solved).
KNOWN_ALGORITHMS = [
    ("R U R' U'", 6),  # the "sexy move"
    ("R U R' U R U2 R'", 6),  # Sune
    ("R U R' U' R' F R2 U' R' U' R U R' F'", 2),  # T perm
    ("R U R' U R U2 R'", 6),
    ("F R U R' U' F'", 6),  # two-look OLL edge case
    ("R2 L2 U2 F2 B2 D2", 2),  # a superflip-like double turn pattern
]


def sequence_of(rng: random.Random, pool: list[str], length: int) -> str:
    """Return a random sequence from a pool of move names."""
    return " ".join(rng.choice(pool) for _ in range(length))


@pytest.mark.parametrize("pool", [FACE_MOVES, FACE_MOVES + ROTATIONS])
def test_cubie_and_facelet_models_agree(pool: list[str]) -> None:
    rng = random.Random(4242)
    for _ in range(300):
        text = sequence_of(rng, pool, 15)
        display = Cube.solved().apply_sequence(text)
        assert display.cubie() == CubieCube.solved().apply_moves(parse_moves(text)), text
        assert display.cubie().to_facelets() == normalized_facelets(display.facelets), text


def test_cubie_and_facelet_models_agree_on_long_sequences() -> None:
    rng = random.Random(31337)
    for _ in range(30):
        text = sequence_of(rng, FACE_MOVES + ROTATIONS, 60)
        display = Cube.solved().apply_sequence(text)
        assert display.cubie() == CubieCube.solved().apply_moves(parse_moves(text)), text


@pytest.mark.parametrize(("algorithm", "order"), KNOWN_ALGORITHMS)
def test_known_algorithm_orders(algorithm: str, order: int) -> None:
    repeated = " ".join([algorithm] * order)
    assert Cube.solved().apply_sequence(repeated).is_solved()
    if order > 1:
        assert not Cube.solved().apply_sequence(" ".join([algorithm] * (order - 1))).is_solved()


def test_a_scramble_and_its_inverse_return_to_solved() -> None:
    rng = random.Random(5)
    for _ in range(100):
        moves = parse_moves(sequence_of(rng, ALL_MOVES, 25))
        scrambled = Cube.solved().apply_moves(moves)
        restored = scrambled.apply_moves([move.inverse() for move in reversed(moves)])
        assert restored.is_solved()


def test_random_walk_stays_consistent_with_the_cubie_model() -> None:
    """Every prefix of a long walk must agree between the two models."""
    rng = random.Random(808)
    text = sequence_of(rng, FACE_MOVES + ROTATIONS, 40)
    names = text.split()
    for length in range(1, len(names) + 1):
        prefix = " ".join(names[:length])
        display = Cube.solved().apply_sequence(prefix)
        assert display.cubie() == CubieCube.solved().apply_moves(parse_moves(prefix)), prefix


def test_normalization_is_stable_under_further_rotations() -> None:
    rng = random.Random(606)
    for _ in range(50):
        scrambled = Cube.solved().apply_sequence(sequence_of(rng, FACE_MOVES, 12))
        canonical = scrambled.normalized()
        for rotation in ROTATIONS:
            assert scrambled.apply_sequence(rotation).normalized() == canonical


@given(st.lists(st.sampled_from(FACE_MOVES), min_size=1, max_size=25))
def test_hypothesis_models_agree(names: list[str]) -> None:
    display = Cube.solved().apply_moves(names)
    assert display.cubie() == CubieCube.solved().apply_moves(names)
    assert display.cubie().to_facelets() == normalized_facelets(display.facelets)


@given(st.lists(st.sampled_from(FACE_MOVES + ROTATIONS), min_size=1, max_size=25))
def test_hypothesis_models_agree_with_rotations(names: list[str]) -> None:
    display = Cube.solved().apply_moves(names)
    assert display.cubie() == CubieCube.solved().apply_moves(names)

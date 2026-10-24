"""Coordinate encodings for the two-phase solver."""

from __future__ import annotations

from itertools import permutations

import pytest

from rubiks_cfop.cube.cubie import CORNER_COUNT, EDGE_COUNT, CubieCube
from rubiks_cfop.solver.coordinates import (
    CORNER_PERM_COUNT,
    EDGE_PERM_COUNT,
    FLIP_COUNT,
    SLICE_COUNT,
    SLICE_PERM_COUNT,
    SOLVED_SLICE,
    TWIST_COUNT,
    UD_EDGE_COUNT,
    combination_index,
    combination_unrank,
    corner_perm,
    edge_perm,
    flip,
    permutation_index,
    permutation_unrank,
    slice_perm,
    slice_position,
    twist,
    with_corner_perm,
    with_edge_perm,
    with_flip,
    with_slice,
    with_slice_perm,
    with_twist,
)


def test_coordinate_sizes() -> None:
    assert TWIST_COUNT == 2187
    assert FLIP_COUNT == 2048
    assert SLICE_COUNT == 495
    assert CORNER_PERM_COUNT == 40320
    assert EDGE_PERM_COUNT == 40320
    assert SLICE_PERM_COUNT == 24
    assert UD_EDGE_COUNT == 8


def test_solved_coordinates() -> None:
    solved = CubieCube.solved()
    assert twist(solved) == 0
    assert flip(solved) == 0
    assert slice_position(solved) == SOLVED_SLICE == 494
    assert corner_perm(solved) == 0
    assert edge_perm(solved) == 0
    assert slice_perm(solved) == 0


def test_combination_round_trip() -> None:
    for index in range(SLICE_COUNT):
        assert combination_index(combination_unrank(index, EDGE_COUNT, 4), 4) == index


def test_combination_index_is_order_independent() -> None:
    assert combination_index([3, 1, 0, 2], 4) == combination_index([0, 1, 2, 3], 4)


@pytest.mark.parametrize(
    ("positions", "size"),
    [([0, 1, 2], 4), ([0, 1, 2, 2], 4), ([], 4)],
)
def test_combination_index_rejects_bad_subsets(positions: list[int], size: int) -> None:
    with pytest.raises(ValueError, match="distinct positions"):
        combination_index(positions, size)


def test_combination_unrank_rejects_bad_index() -> None:
    with pytest.raises(ValueError, match="index must be between"):
        combination_unrank(SLICE_COUNT, EDGE_COUNT, 4)


def test_permutation_round_trip_for_four() -> None:
    for index, permutation in enumerate(permutations(range(4))):
        assert permutation_index(permutation) == index
        assert permutation_unrank(index, 4) == permutation


def test_permutation_round_trip_for_eight() -> None:
    for index in range(CORNER_PERM_COUNT):
        assert permutation_index(permutation_unrank(index, CORNER_COUNT)) == index


def test_permutation_unrank_rejects_bad_index() -> None:
    with pytest.raises(ValueError, match="index must be between"):
        permutation_unrank(CORNER_PERM_COUNT, CORNER_COUNT)


def test_twist_round_trip() -> None:
    solved = CubieCube.solved()
    assert len({twist(with_twist(solved, value)) for value in range(TWIST_COUNT)}) == TWIST_COUNT
    for value in range(TWIST_COUNT):
        assert twist(with_twist(solved, value)) == value


def test_flip_round_trip() -> None:
    solved = CubieCube.solved()
    for value in range(FLIP_COUNT):
        assert flip(with_flip(solved, value)) == value


def test_slice_round_trip() -> None:
    solved = CubieCube.solved()
    for value in range(SLICE_COUNT):
        state = with_slice(solved, value)
        assert slice_position(state) == value
        assert sorted(state.ep) == list(range(EDGE_COUNT))


def test_permutation_coordinate_round_trips() -> None:
    solved = CubieCube.solved()
    for value in range(CORNER_PERM_COUNT):
        assert corner_perm(with_corner_perm(solved, value)) == value
    for value in range(EDGE_PERM_COUNT):
        assert edge_perm(with_edge_perm(solved, value)) == value
    for value in range(SLICE_PERM_COUNT):
        assert slice_perm(with_slice_perm(solved, value)) == value


def test_orientations_are_repaired_by_the_last_piece() -> None:
    solved = CubieCube.solved()
    for value in range(TWIST_COUNT):
        assert sum(with_twist(solved, value).co) % 3 == 0
    for value in range(FLIP_COUNT):
        assert sum(with_flip(solved, value).eo) % 2 == 0

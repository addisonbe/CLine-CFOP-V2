"""Coordinate encodings for the two-phase solver.

A two-phase solve reasons about four numbers at a time rather than 20 cubies, so
each phase needs compact coordinates with cheap, precomputable moves:

===============  ==============  ==========================================
Coordinate       Values          Meaning
===============  ==============  ==========================================
``twist``        2187 = 3^7      orientation of the eight corners
``flip``         2048 = 2^11     orientation of the twelve edges
``slice``        495 = C(12, 4)   which positions hold the four slice edges
``corner_perm``  40320 = 8!      permutation of the eight corners
``edge_perm``    40320 = 8!      permutation of the eight up/down edges
``slice_perm``   24 = 4!         permutation of the four slice edges
===============  ==============  ==========================================

Phase 1 solves ``twist``, ``flip`` and ``slice``; phase 2 then solves
``corner_perm``, ``edge_perm`` and ``slice_perm`` using only moves that keep the
first three at zero.

Every coordinate is 0 when solved, except ``slice``, which is 0 when the slice
edges sit in the first four positions and 494 -- its maximum -- when they are
home.  :data:`SOLVED_SLICE` records that value so callers never hard-code it.
"""

from __future__ import annotations

from dataclasses import replace
from math import comb, factorial
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.cubie import CORNER_COUNT, EDGE_COUNT, CubieCube

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

__all__ = [
    "CORNER_PERM_COUNT",
    "EDGE_PERM_COUNT",
    "FLIP_COUNT",
    "SLICE_COUNT",
    "SLICE_PERM_COUNT",
    "SOLVED_SLICE",
    "TWIST_COUNT",
    "UD_EDGE_COUNT",
    "combination_index",
    "combination_unrank",
    "corner_perm",
    "edge_perm",
    "flip",
    "permutation_index",
    "permutation_unrank",
    "slice_perm",
    "slice_position",
    "twist",
    "with_corner_perm",
    "with_edge_perm",
    "with_flip",
    "with_slice",
    "with_slice_perm",
    "with_twist",
]

#: The first eight edges in Kociemba order are the up/down edges.
UD_EDGE_COUNT: Final = 8

#: The four slice edges (FR, FL, BL, BR) and their cubie indices.
SLICE_EDGES: Final[tuple[int, ...]] = (8, 9, 10, 11)
SLICE_EDGE_COUNT: Final = len(SLICE_EDGES)

TWIST_COUNT: Final = 3**7
FLIP_COUNT: Final = 2**11
SLICE_COUNT: Final = comb(EDGE_COUNT, SLICE_EDGE_COUNT)
CORNER_PERM_COUNT: Final = factorial(CORNER_COUNT)
EDGE_PERM_COUNT: Final = factorial(UD_EDGE_COUNT)
SLICE_PERM_COUNT: Final = factorial(SLICE_EDGE_COUNT)

# ---------------------------------------------------------------------------
# Generic combinatorial helpers
# ---------------------------------------------------------------------------


def combination_index(positions: Iterable[int], size: int) -> int:
    """Rank a ``size`` element subset of the positions ``0..n-1``.

    Uses the combinatorial number system: the subset is ranked by
    ``sum(C(position, rank))`` over its sorted positions.

    Args:
        positions: The positions in the subset; order does not matter.
        size: How many positions the subset must contain.

    Returns:
        The rank, between 0 and ``C(n, size) - 1``.

    Raises:
        ValueError: If the subset does not have exactly ``size`` distinct members.
    """
    ordered = sorted(positions)
    if len(ordered) != size or len(set(ordered)) != size:
        msg = f"expected {size} distinct positions, got {len(ordered)}"
        raise ValueError(msg)
    return sum(comb(position, rank + 1) for rank, position in enumerate(ordered))


#: The slice coordinate of a solved cube.
SOLVED_SLICE: Final = combination_index(SLICE_EDGES, SLICE_EDGE_COUNT)


def combination_unrank(index: int, size: int, subset_size: int) -> tuple[int, ...]:
    """Return the sorted positions of the subset with a given rank.

    Args:
        index: The rank produced by :func:`combination_index`.
        size: The number of available positions.
        subset_size: How many positions the subset contains.

    Returns:
        The positions, sorted ascending.

    Raises:
        ValueError: If ``index`` is out of range.
    """
    if not 0 <= index < comb(size, subset_size):
        msg = f"index must be between 0 and {comb(size, subset_size) - 1}, got {index}"
        raise ValueError(msg)
    chosen: list[int] = []
    remaining = index
    for rank in range(subset_size, 0, -1):
        position = rank - 1
        while position + 1 < size and comb(position + 1, rank) <= remaining:
            position += 1
        chosen.append(position)
        remaining -= comb(position, rank)
    return tuple(sorted(chosen))


def permutation_index(permutation: Sequence[int]) -> int:
    """Rank a permutation of ``0..n-1`` by its Lehmer code.

    Args:
        permutation: The permutation.

    Returns:
        The rank, between 0 and ``n! - 1``; the identity ranks 0.
    """
    size = len(permutation)
    index = 0
    for position, value in enumerate(permutation):
        smaller = 0
        for other in permutation[position + 1 :]:
            if other < value:
                smaller += 1
        index = index * (size - position) + smaller
    return index


def permutation_unrank(index: int, size: int) -> tuple[int, ...]:
    """Return the permutation with a given rank.

    Args:
        index: The rank produced by :func:`permutation_index`.
        size: The number of elements.

    Returns:
        The permutation of ``0..size-1``.

    Raises:
        ValueError: If ``index`` is out of range.
    """
    if not 0 <= index < factorial(size):
        msg = f"index must be between 0 and {factorial(size) - 1}, got {index}"
        raise ValueError(msg)
    available = list(range(size))
    permutation: list[int] = []
    remaining = index
    for position in range(size):
        block = factorial(size - position - 1)
        digit, remaining = divmod(remaining, block)
        permutation.append(available.pop(digit))
    return tuple(permutation)


# ---------------------------------------------------------------------------
# Corner orientation
# ---------------------------------------------------------------------------


def twist(cubie: CubieCube) -> int:
    """Return the corner orientation coordinate, 0 when every corner is upright."""
    value = 0
    for orientation in reversed(cubie.co[: CORNER_COUNT - 1]):
        value = value * 3 + orientation
    return value


def with_twist(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` carrying the given corner orientation coordinate.

    The eighth corner is derived, because the eight orientations must sum to a
    multiple of three.
    """
    co = list(cubie.co)
    total = 0
    remaining = value
    for index in range(CORNER_COUNT - 1):
        co[index] = remaining % 3
        total += co[index]
        remaining //= 3
    co[CORNER_COUNT - 1] = (-total) % 3
    return replace(cubie, co=tuple(co))


# ---------------------------------------------------------------------------
# Edge orientation
# ---------------------------------------------------------------------------


def flip(cubie: CubieCube) -> int:
    """Return the edge orientation coordinate, 0 when every edge is unflipped."""
    value = 0
    for orientation in reversed(cubie.eo[: EDGE_COUNT - 1]):
        value = value * 2 + orientation
    return value


def with_flip(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` carrying the given edge orientation coordinate."""
    eo = list(cubie.eo)
    total = 0
    remaining = value
    for index in range(EDGE_COUNT - 1):
        eo[index] = remaining % 2
        total += eo[index]
        remaining //= 2
    eo[EDGE_COUNT - 1] = total % 2
    return replace(cubie, eo=tuple(eo))


# ---------------------------------------------------------------------------
# Slice
# ---------------------------------------------------------------------------


def slice_position(cubie: CubieCube) -> int:
    """Return which positions hold the four slice edges, as a rank."""
    return combination_index(
        (index for index, cubie_id in enumerate(cubie.ep) if cubie_id >= UD_EDGE_COUNT),
        SLICE_EDGE_COUNT,
    )


def with_slice(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` whose slice edges occupy the ranked positions."""
    positions = set(combination_unrank(value, EDGE_COUNT, SLICE_EDGE_COUNT))
    ep = [0] * EDGE_COUNT
    slice_cubies = list(SLICE_EDGES)
    ud_cubies = list(range(UD_EDGE_COUNT))
    for position in range(EDGE_COUNT):
        ep[position] = slice_cubies.pop(0) if position in positions else ud_cubies.pop(0)
    return replace(cubie, ep=tuple(ep))


# ---------------------------------------------------------------------------
# Permutations
# ---------------------------------------------------------------------------


def corner_perm(cubie: CubieCube) -> int:
    """Return the rank of the corner permutation."""
    return permutation_index(cubie.cp)


def with_corner_perm(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` with the corner permutation of a given rank."""
    return replace(cubie, cp=permutation_unrank(value, CORNER_COUNT))


def edge_perm(cubie: CubieCube) -> int:
    """Return the rank of the up/down edge permutation."""
    return permutation_index(cubie.ep[:UD_EDGE_COUNT])


def with_edge_perm(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` with the up/down edges permuted to a given rank."""
    ep = list(cubie.ep)
    ep[:UD_EDGE_COUNT] = permutation_unrank(value, UD_EDGE_COUNT)
    return replace(cubie, ep=tuple(ep))


def slice_perm(cubie: CubieCube) -> int:
    """Return the rank of the slice edge permutation."""
    return permutation_index(
        [cubie.ep[index] - UD_EDGE_COUNT for index in range(UD_EDGE_COUNT, EDGE_COUNT)]
    )


def with_slice_perm(cubie: CubieCube, value: int) -> CubieCube:
    """Return a copy of ``cubie`` with the slice edges permuted to a given rank."""
    ep = list(cubie.ep)
    for offset, cubie_id in enumerate(permutation_unrank(value, SLICE_EDGE_COUNT)):
        ep[UD_EDGE_COUNT + offset] = UD_EDGE_COUNT + cubie_id
    return replace(cubie, ep=tuple(ep))

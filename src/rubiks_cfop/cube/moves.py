"""Move tables for the 3x3x3 cube, derived from the cube's geometry.

Every move is a permutation of the 54 Kociemba facelets.  The permutations are
generated from first principles instead of being copied from a table: each
facelet is described by the coordinate of the cubie that carries it plus the
facelet's outward normal, and a move is a right-handed rotation of a set of
layers about one axis.  A face turn clockwise as seen from outside the face is a
right-handed rotation of -90 degrees about that face's outward normal.

The generated tables are checked against Kociemba's published facelet
permutations in ``tests/test_kociemba_reference.py``.

Supported moves
---------------
=================  =========================================================
Face turns         ``U U2 U' R R2 R' F F2 F' D D2 D' L L2 L' B B2 B'``
(WCA 12a1)
Wide turns         ``Uw Uw2 Uw' Dw Dw2 Dw' Lw Lw2 Lw' Rw Rw2 Rw'``
(WCA 12a2)         ``Fw Fw2 Fw' Bw Bw2 Bw'`` (``2Rw`` means the same as ``Rw``)
Rotations          ``x x2 x' y y2 y' z z2 z'``
(WCA 12a4)
Slice turns        ``M M2 M' E E2 E' S S2 S'``
(extension)
=================  =========================================================

Slice turns are not part of WCA notation, but many published OLL/PLL algorithms
use them, so the engine understands them as a documented extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Final

from rubiks_cfop.cube.facelets import (
    FACE_ORDER,
    FACELET_COUNT,
    SOLVED_FACELETS,
    Face,
    facelet_index,
)
from rubiks_cfop.errors import InvalidMoveError, InvalidStateError

__all__ = [
    "BASE_MOVE_NAMES",
    "MOVES",
    "MOVE_NAMES",
    "Move",
    "MoveKind",
    "compose",
    "conjugate",
    "get_move",
    "invert",
    "invert_permutation",
    "move_names",
    "normalized_facelets",
    "rotation_to_normalize",
    "rotations",
]

_Vector = tuple[int, int, int]

_QUARTER: Final = 90
_MINUS_QUARTER: Final = -90
_ALL_LAYERS: Final = (-1, 0, 1)


class MoveKind(StrEnum):
    """The family a move belongs to."""

    FACE = "face"
    WIDE = "wide"
    SLICE = "slice"
    ROTATION = "rotation"


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

_AXIS_INDEX: Final[dict[str, int]] = {"x": 0, "y": 1, "z": 2}

#: Outward normal of each face, in the cube's own coordinate system
#: (x right, y up, z towards the viewer).
_FACE_NORMAL: Final[dict[Face, _Vector]] = {
    Face.U: (0, 1, 0),
    Face.R: (1, 0, 0),
    Face.F: (0, 0, 1),
    Face.D: (0, -1, 0),
    Face.L: (-1, 0, 0),
    Face.B: (0, 0, -1),
}

#: For each face: the cubie coordinate of the top-left facelet, plus the step
#: taken per grid row and per grid column.  These are exactly Kociemba's
#: facelet conventions (see the module docstring of ``facelets``).
_STICKER_LAYOUT: Final[dict[Face, tuple[_Vector, _Vector, _Vector]]] = {
    Face.U: ((-1, 1, -1), (0, 0, 1), (1, 0, 0)),
    Face.R: ((1, 1, 1), (0, -1, 0), (0, 0, -1)),
    Face.F: ((-1, 1, 1), (0, -1, 0), (1, 0, 0)),
    Face.D: ((-1, -1, 1), (0, 0, -1), (1, 0, 0)),
    Face.L: ((-1, 1, -1), (0, -1, 0), (0, 0, 1)),
    Face.B: ((1, 1, -1), (0, -1, 0), (-1, 0, 0)),
}


def _rotate(vector: _Vector, axis: str, degrees: int) -> _Vector:
    """Rotate ``vector`` right-handed about ``axis`` by +90 or -90 degrees."""
    x, y, z = vector
    match axis:
        case "x":
            return (x, -z, y) if degrees == _QUARTER else (x, z, -y)
        case "y":
            return (z, y, -x) if degrees == _QUARTER else (-z, y, x)
        case _:
            return (-y, x, z) if degrees == _QUARTER else (y, -x, z)


def _build_stickers() -> tuple[tuple[_Vector, _Vector], ...]:
    """Return ``(cubie position, outward normal)`` for all 54 facelets."""
    stickers: list[tuple[_Vector, _Vector]] = []
    for face in FACE_ORDER:
        normal = _FACE_NORMAL[face]
        base, row_step, col_step = _STICKER_LAYOUT[face]
        for row in range(3):
            for col in range(3):
                position: _Vector = (
                    base[0] + row * row_step[0] + col * col_step[0],
                    base[1] + row * row_step[1] + col * col_step[1],
                    base[2] + row * row_step[2] + col * col_step[2],
                )
                stickers.append((position, normal))
    return tuple(stickers)


_STICKERS: Final = _build_stickers()

_STICKER_INDEX: Final[dict[tuple[_Vector, _Vector], int]] = {
    sticker: index for index, sticker in enumerate(_STICKERS)
}


def _permutation(axis: str, layers: tuple[int, ...], degrees: int) -> tuple[int, ...]:
    """Return the "is carried to" permutation of a layer rotation.

    ``result[i]`` is the facelet that the sticker at facelet ``i`` moves to.
    """
    axis_index = _AXIS_INDEX[axis]
    carried_to = list(range(FACELET_COUNT))
    for index, (position, normal) in enumerate(_STICKERS):
        if position[axis_index] not in layers:
            continue
        carried_to[index] = _STICKER_INDEX[
            (_rotate(position, axis, degrees), _rotate(normal, axis, degrees))
        ]
    return tuple(carried_to)


def compose(first: tuple[int, ...], second: tuple[int, ...]) -> tuple[int, ...]:
    """Return the permutation that applies ``first`` and then ``second``."""
    return tuple(second[first[index]] for index in range(FACELET_COUNT))


def invert_permutation(permutation: tuple[int, ...]) -> tuple[int, ...]:
    """Return the inverse of a facelet permutation."""
    inverse = [0] * FACELET_COUNT
    for index, target in enumerate(permutation):
        inverse[target] = index
    return tuple(inverse)


def conjugate(permutation: tuple[int, ...], frame: tuple[int, ...]) -> tuple[int, ...]:
    """Return ``permutation`` expressed in the frame ``frame``.

    Conjugating a move by a whole cube rotation yields the same physical turn
    applied to the rotated face, which is how a move named in a rotated display
    has to be interpreted.
    """
    return compose(frame, compose(permutation, invert_permutation(frame)))


# ---------------------------------------------------------------------------
# Move definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _BaseMove:
    """A quarter turn, from which the three canonical spellings are derived."""

    name: str
    kind: MoveKind
    axis: str
    layers: tuple[int, ...]
    degrees: int
    face: Face | None


#: Slice turns follow the direction of the face they sit next to, rotations
#: follow the direction of R, U and F (WCA Regulation 12a4).
_BASE_MOVES: Final[tuple[_BaseMove, ...]] = (
    _BaseMove("U", MoveKind.FACE, "y", (1,), _MINUS_QUARTER, Face.U),
    _BaseMove("D", MoveKind.FACE, "y", (-1,), _QUARTER, Face.D),
    _BaseMove("R", MoveKind.FACE, "x", (1,), _MINUS_QUARTER, Face.R),
    _BaseMove("L", MoveKind.FACE, "x", (-1,), _QUARTER, Face.L),
    _BaseMove("F", MoveKind.FACE, "z", (1,), _MINUS_QUARTER, Face.F),
    _BaseMove("B", MoveKind.FACE, "z", (-1,), _QUARTER, Face.B),
    _BaseMove("Uw", MoveKind.WIDE, "y", (1, 0), _MINUS_QUARTER, Face.U),
    _BaseMove("Dw", MoveKind.WIDE, "y", (-1, 0), _QUARTER, Face.D),
    _BaseMove("Rw", MoveKind.WIDE, "x", (1, 0), _MINUS_QUARTER, Face.R),
    _BaseMove("Lw", MoveKind.WIDE, "x", (-1, 0), _QUARTER, Face.L),
    _BaseMove("Fw", MoveKind.WIDE, "z", (1, 0), _MINUS_QUARTER, Face.F),
    _BaseMove("Bw", MoveKind.WIDE, "z", (-1, 0), _QUARTER, Face.B),
    _BaseMove("M", MoveKind.SLICE, "x", (0,), _QUARTER, None),
    _BaseMove("E", MoveKind.SLICE, "y", (0,), _QUARTER, None),
    _BaseMove("S", MoveKind.SLICE, "z", (0,), _MINUS_QUARTER, None),
    _BaseMove("x", MoveKind.ROTATION, "x", _ALL_LAYERS, _MINUS_QUARTER, None),
    _BaseMove("y", MoveKind.ROTATION, "y", _ALL_LAYERS, _MINUS_QUARTER, None),
    _BaseMove("z", MoveKind.ROTATION, "z", _ALL_LAYERS, _MINUS_QUARTER, None),
)

_SUFFIXES: Final[tuple[tuple[str, int], ...]] = (("", 1), ("2", 2), ("'", 3))


@dataclass(frozen=True, slots=True)
class Move:
    """A single move of the cube, stored as its facelet permutation.

    Attributes:
        name: Canonical name, for example ``R``, ``R2``, ``R'`` or ``Rw``.
        base: The name without its turn suffix, for example ``R`` or ``Rw``.
        turns: Number of quarter turns, 1, 2 or 3.
        kind: Whether this is a face, wide, slice or rotation move.
        face: The face the move belongs to, if it has one.
        carried_to: ``carried_to[i]`` is the facelet that the sticker at facelet
            ``i`` moves to, matching Kociemba's "is carried to" representation.
        replaced_by: Inverse of ``carried_to``; ``replaced_by[i]`` is the facelet
            whose sticker ends up at facelet ``i``.
    """

    name: str
    base: str
    turns: int
    kind: MoveKind
    face: Face | None
    carried_to: tuple[int, ...]
    replaced_by: tuple[int, ...]

    def apply_to(self, facelets: str) -> str:
        """Return the facelet string after applying this move.

        Raises:
            ValueError: If ``facelets`` is not a 54 character string.
        """
        if len(facelets) != FACELET_COUNT:
            msg = f"a cube state has {FACELET_COUNT} facelets, got {len(facelets)}"
            raise ValueError(msg)
        return "".join(facelets[index] for index in self.replaced_by)

    def inverse(self) -> Move:
        """Return the move that undoes this one."""
        return MOVES[_invert_name(self.name)]


def _build_moves() -> dict[str, Move]:
    """Build the 54 canonical moves (18 bases times three turn suffixes)."""
    moves: dict[str, Move] = {}
    for base in _BASE_MOVES:
        quarter = _permutation(base.axis, base.layers, base.degrees)
        permutations = {"": quarter, "2": compose(quarter, quarter)}
        permutations["'"] = compose(permutations["2"], quarter)
        for suffix, turns in _SUFFIXES:
            carried_to = permutations[suffix]
            name = f"{base.name}{suffix}"
            moves[name] = Move(
                name=name,
                base=base.name,
                turns=turns,
                kind=base.kind,
                face=base.face,
                carried_to=carried_to,
                replaced_by=invert_permutation(carried_to),
            )
    return moves


#: All canonical moves, keyed by name.
MOVES: Final[dict[str, Move]] = _build_moves()

#: The 18 quarter turn bases, in definition order.
BASE_MOVE_NAMES: Final[tuple[str, ...]] = tuple(base.name for base in _BASE_MOVES)

#: All canonical move names, in definition order.
MOVE_NAMES: Final[tuple[str, ...]] = tuple(MOVES)


def _invert_name(name: str) -> str:
    """Return the name of the inverse of a canonical move name."""
    if name.endswith("'"):
        return name[:-1]
    if name.endswith("2"):
        return name
    return f"{name}'"


def get_move(name: str) -> Move:
    """Return a move by its canonical name.

    Args:
        name: A canonical name such as ``R``, ``R2``, ``R'``, ``Rw``, ``x`` or ``M``.

    Returns:
        The matching move.

    Raises:
        InvalidMoveError: If ``name`` is not a canonical move name.
    """
    try:
        return MOVES[name]
    except KeyError as exc:
        raise InvalidMoveError("unknown move", move=name) from exc


def invert(move: Move) -> Move:
    """Return the move that undoes ``move``."""
    return MOVES[_invert_name(move.name)]


def move_names() -> tuple[str, ...]:
    """Return every canonical move name, in a stable order."""
    return MOVE_NAMES


# ---------------------------------------------------------------------------
# Whole cube rotations
# ---------------------------------------------------------------------------

_CENTER_INDICES: Final[tuple[int, ...]] = tuple(facelet_index(face, 5) for face in FACE_ORDER)


def _apply_sequence(facelets: str, names: tuple[str, ...]) -> str:
    """Apply a sequence of canonical move names to a facelet string."""
    for name in names:
        facelets = MOVES[name].apply_to(facelets)
    return facelets


def _center_key(facelets: str) -> str:
    """Return the six centre letters of a facelet string, in face order."""
    return "".join(facelets[index] for index in _CENTER_INDICES)


def _invert_sequence(names: tuple[str, ...]) -> tuple[str, ...]:
    """Return the sequence that undoes ``names``."""
    return tuple(_invert_name(name) for name in reversed(names))


@lru_cache(maxsize=1)
def rotations() -> tuple[tuple[str, ...], ...]:
    """Return all 24 whole cube rotations, each as a sequence of rotation moves.

    The rotations are found by breadth first search over ``x``, ``y`` and ``z``
    until no new permutation appears, so the list is complete by construction.
    """
    identity: tuple[str, ...] = ()
    seen: dict[tuple[int, ...], tuple[str, ...]] = {tuple(range(FACELET_COUNT)): identity}
    queue = [identity]
    while queue:
        sequence = queue.pop()
        for base in ("x", "y", "z"):
            candidate = (*sequence, base)
            permutation = tuple(range(FACELET_COUNT))
            for name in candidate:
                permutation = compose(permutation, MOVES[name].carried_to)
            if permutation not in seen:
                seen[permutation] = candidate
                queue.append(candidate)
    return tuple(seen.values())


@lru_cache(maxsize=1)
def _normalizing_rotations() -> dict[str, tuple[str, ...]]:
    """Map a centre arrangement to the rotation that puts the centres back."""
    lookup: dict[str, tuple[str, ...]] = {}
    for sequence in rotations():
        rotated = _apply_sequence(SOLVED_FACELETS, sequence)
        lookup[_center_key(rotated)] = _invert_sequence(sequence)
    return lookup


def rotation_to_normalize(facelets: str) -> tuple[str, ...]:
    """Return the whole cube rotation that puts the centres back in place.

    Args:
        facelets: A facelet string.

    Returns:
        A rotation sequence, empty when the centres are already canonical.

    Raises:
        InvalidStateError: If the centre colours are not a rotation of the solved
            arrangement, in which case the state is not a cube.
    """
    key = _center_key(facelets)
    try:
        return _normalizing_rotations()[key]
    except KeyError as exc:
        raise InvalidStateError(
            "the centre colours are not a rotation of a solved cube",
            centers=key,
        ) from exc


def normalized_facelets(facelets: str) -> str:
    """Return ``facelets`` with any whole cube rotation undone.

    This is the canonical form used by the cubie level model and by the solvers:
    the same physical cube, described with the centres in their home faces.

    Raises:
        InvalidStateError: If the centre colours are not a valid rotation.
    """
    return _apply_sequence(facelets, rotation_to_normalize(facelets))

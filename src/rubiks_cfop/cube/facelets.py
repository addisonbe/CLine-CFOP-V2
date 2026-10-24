"""Kociemba facelet representation of the 3x3x3 cube.

Facelets are numbered in Kociemba's canonical order::

    U1..U9  R1..R9  F1..F9  D1..D9  L1..L9  B1..B9

so the solved cube is the 54 character string
``UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB``.

Inside a face, facelets are numbered row by row in reading order as seen from
outside the cube.  The "view up" direction of each face, and therefore which
corner the first facelet belongs to, is fixed by Kociemba's own move
definitions:

=========  =============  =========================
Face       view up        first facelet belongs to
=========  =============  =========================
``U``      back (-z)      UBL
``R``      up (+y)        UFR
``F``      up (+y)        UFL
``D``      front (+z)     DFL
``L``      up (+y)        UBL
``B``      up (+y)        UBR
=========  =============  =========================

Colours follow the standard WCA scheme (Regulation 4d1: white on top, green in
front): ``U`` white, ``R`` red, ``F`` green, ``D`` yellow, ``L`` orange and
``B`` blue.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from rubiks_cfop.errors import InvalidStateError

__all__ = [
    "COLOR_FACE",
    "FACELETS_PER_FACE",
    "FACELET_COUNT",
    "FACES_PER_CUBE",
    "FACE_COLOR",
    "FACE_ORDER",
    "SOLVED_FACELETS",
    "Color",
    "Face",
    "canonicalize_colors",
    "centers_are_canonical",
    "face_facelets",
    "face_index",
    "face_of",
    "facelet",
    "facelet_index",
    "facelet_name",
    "facelets_of_face",
    "index_of_name",
    "is_solved_facelets",
    "normalize_facelets",
    "validate_facelets",
]


class Face(StrEnum):
    """One of the six faces, in Kociemba's canonical order."""

    U = "U"
    R = "R"
    F = "F"
    D = "D"
    L = "L"
    B = "B"


class Color(StrEnum):
    """One of the six sticker colours of the standard WCA colour scheme."""

    WHITE = "white"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    BLUE = "blue"


#: A facelet name such as ``U1`` has a letter and a digit.
FACELET_NAME_LENGTH: Final = 2

FACES_PER_CUBE: Final = 6
FACELETS_PER_FACE: Final = 9
FACELET_COUNT: Final = FACES_PER_CUBE * FACELETS_PER_FACE

#: Faces in Kociemba facelet order.
FACE_ORDER: Final[tuple[Face, ...]] = (Face.U, Face.R, Face.F, Face.D, Face.L, Face.B)

#: The solved cube as a Kociemba facelet string.
SOLVED_FACELETS: Final = "".join(face.value * FACELETS_PER_FACE for face in FACE_ORDER)

#: Standard colour scheme (WCA Regulation 4d1: white up, green front).
FACE_COLOR: Final[dict[Face, Color]] = {
    Face.U: Color.WHITE,
    Face.R: Color.RED,
    Face.F: Color.GREEN,
    Face.D: Color.YELLOW,
    Face.L: Color.ORANGE,
    Face.B: Color.BLUE,
}

#: Inverse of :data:`FACE_COLOR`.
COLOR_FACE: Final[dict[Color, Face]] = {color: face for face, color in FACE_COLOR.items()}

_FACE_OFFSET: Final[dict[Face, int]] = {
    face: offset * FACELETS_PER_FACE for offset, face in enumerate(FACE_ORDER)
}

_VALID_FACELET_LETTERS: Final[frozenset[str]] = frozenset(face.value for face in FACE_ORDER)


def face_index(face: Face | str) -> int:
    """Return the position of ``face`` in :data:`FACE_ORDER` (0 for ``U``).

    Args:
        face: Face name, either a :class:`Face` or its one letter string.

    Returns:
        The zero-based face index.

    Raises:
        KeyError: If ``face`` is not a valid face name.
    """
    return FACE_ORDER.index(Face(face))


def facelet_index(face: Face | str, position: int) -> int:
    """Return the global facelet index (0-53) of a position on a face.

    Args:
        face: Face name, either a :class:`Face` or its one letter string.
        position: One-based position within the face, 1 to 9.

    Returns:
        The zero-based global facelet index.

    Raises:
        KeyError: If ``face`` is not a valid face name.
        ValueError: If ``position`` is outside 1 to 9.
    """
    if not 1 <= position <= FACELETS_PER_FACE:
        msg = f"facelet position must be between 1 and {FACELETS_PER_FACE}, got {position}"
        raise ValueError(msg)
    return _FACE_OFFSET[Face(face)] + position - 1


def facelet_name(index: int) -> str:
    """Return the Kociemba name (``U1`` to ``B9``) of a global facelet index.

    Raises:
        ValueError: If ``index`` is outside 0 to 53.
    """
    if not 0 <= index < FACELET_COUNT:
        msg = f"facelet index must be between 0 and {FACELET_COUNT - 1}, got {index}"
        raise ValueError(msg)
    face = FACE_ORDER[index // FACELETS_PER_FACE]
    return f"{face.value}{index % FACELETS_PER_FACE + 1}"


def index_of_name(name: str) -> int:
    """Return the global facelet index of a Kociemba facelet name such as ``U1``.

    Raises:
        ValueError: If ``name`` is not a facelet name.
    """
    text = name.strip().upper()
    if (
        len(text) != FACELET_NAME_LENGTH
        or text[0] not in _VALID_FACELET_LETTERS
        or text[1] not in "123456789"
    ):
        msg = f"not a facelet name: {name!r}"
        raise ValueError(msg)
    return facelet_index(Face(text[0]), int(text[1]))


def face_of(index: int) -> Face:
    """Return the face a global facelet index belongs to."""
    if not 0 <= index < FACELET_COUNT:
        msg = f"facelet index must be between 0 and {FACELET_COUNT - 1}, got {index}"
        raise ValueError(msg)
    return FACE_ORDER[index // FACELETS_PER_FACE]


def facelets_of_face(face: Face | str) -> tuple[int, ...]:
    """Return the nine global facelet indices of ``face``, in reading order."""
    offset = _FACE_OFFSET[Face(face)]
    return tuple(range(offset, offset + FACELETS_PER_FACE))


def normalize_facelets(text: str) -> str:
    """Strip whitespace and upper-case a facelet string."""
    return "".join(text.split()).upper()


def validate_facelets(text: str) -> str:
    """Validate a facelet string and return its normalised form.

    A string is valid when it has 54 characters, uses only the letters
    ``U R F D L B``, contains each letter exactly nine times and keeps the six
    centre facelets in place.  Solvability (orientation sums and permutation
    parity) is checked separately by :mod:`rubiks_cfop.cube.cubie`.

    Args:
        text: The facelet string, optionally containing whitespace.

    Returns:
        The normalised 54 character facelet string.

    Raises:
        InvalidStateError: If the string is not a well formed cube state.
    """
    normalized = normalize_facelets(text)
    if len(normalized) != FACELET_COUNT:
        raise InvalidStateError(
            f"a cube state has {FACELET_COUNT} facelets",
            length=len(normalized),
        )
    unknown = sorted(set(normalized) - _VALID_FACELET_LETTERS)
    if unknown:
        raise InvalidStateError("unknown facelet letters", letters=unknown)
    counts = {letter: normalized.count(letter) for letter in sorted(_VALID_FACELET_LETTERS)}
    wrong = {letter: count for letter, count in counts.items() if count != FACELETS_PER_FACE}
    if wrong:
        raise InvalidStateError("each colour must appear exactly nine times", counts=wrong)
    return normalized


def centers_are_canonical(text: str) -> bool:
    """Return whether every centre facelet carries its own face's colour.

    Whole cube rotations move the centres, so a state is *canonical* only when no
    rotation has been applied to it.  ``normalized_facelets`` turns any state into
    that form.
    """
    normalized = normalize_facelets(text)
    return all(normalized[facelet_index(face, 5)] == face.value for face in FACE_ORDER)


def canonicalize_colors(text: str) -> str:
    """Relabel the colours so that every centre carries its own face's colour.

    A whole cube rotation permutes which colours appear on which face.  Relabelling
    the colours -- instead of moving the stickers -- keeps the physical arrangement
    intact while naming the faces the way the viewer sees them: the colour on the
    bottom face becomes ``D``, the one on the front becomes ``F``, and so on.  The
    solvers' piece coordinates are expressed in this frame.

    Args:
        text: A facelet string.

    Returns:
        The relabelled string, with canonical centres.

    Raises:
        InvalidStateError: If the six centres are not six distinct colours.
    """
    normalized = normalize_facelets(text)
    mapping: dict[str, str] = {}
    for face in FACE_ORDER:
        center = normalized[facelet_index(face, 5)]
        if center in mapping:
            raise InvalidStateError("the six centre colours must be distinct")
        mapping[center] = face.value
    return "".join(mapping[letter] for letter in normalized)


def is_solved_facelets(text: str) -> bool:
    """Return whether ``text`` is the solved cube, ignoring whitespace and case."""
    return normalize_facelets(text) == SOLVED_FACELETS


def facelet(facelets: str, name: str) -> str:
    """Return the letter of a named facelet, for example ``facelet(s, "U1")``."""
    return facelets[index_of_name(name)]


def face_facelets(facelets: str, face: Face | str) -> str:
    """Return the nine facelets of ``face`` as a string, in reading order."""
    return "".join(facelets[index] for index in facelets_of_face(face))

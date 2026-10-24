"""Kociemba's published move definitions, used as an independent test oracle.

The data below is transcribed from ``https://kociemba.org/math/CubeDefs.htm``,
where the six face turns are given as ``FaceletMove`` in "is carried to"
representation over the facelet order
``U1..U9 R1..R9 F1..F9 D1..D9 L1..L9 B1..B9``.

This is deliberately *not* derived from the engine: it lets the tests check the
geometrically generated move tables against an authoritative external source.
"""

from __future__ import annotations

from typing import Final

from rubiks_cfop.cube.facelets import FACE_ORDER, Face

__all__ = ["FACELET_NAMES", "KOCIEMBA_FACE_MOVES", "facelet_index_of_name"]

FACELET_NAMES: Final[tuple[str, ...]] = tuple(
    f"{face.value}{position}" for face in FACE_ORDER for position in range(1, 10)
)


def facelet_index_of_name(name: str) -> int:
    """Return the global facelet index of a Kociemba facelet name."""
    return FACE_ORDER.index(Face(name[0])) * 9 + int(name[1]) - 1


#: The six face turns, transcribed verbatim from Kociemba's ``FaceletMove``.
_KOCIEMBA_RAW: Final[dict[str, str]] = {
    "U": (
        "U3 U6 U9 U2 U5 U8 U1 U4 U7 "
        "F1 F2 F3 R4 R5 R6 R7 R8 R9 "
        "L1 L2 L3 F4 F5 F6 F7 F8 F9 "
        "D1 D2 D3 D4 D5 D6 D7 D8 D9 "
        "B1 B2 B3 L4 L5 L6 L7 L8 L9 "
        "R1 R2 R3 B4 B5 B6 B7 B8 B9"
    ),
    "R": (
        "U1 U2 B7 U4 U5 B4 U7 U8 B1 "
        "R3 R6 R9 R2 R5 R8 R1 R4 R7 "
        "F1 F2 U3 F4 F5 U6 F7 F8 U9 "
        "D1 D2 F3 D4 D5 F6 D7 D8 F9 "
        "L1 L2 L3 L4 L5 L6 L7 L8 L9 "
        "D9 B2 B3 D6 B5 B6 D3 B8 B9"
    ),
    "F": (
        "U1 U2 U3 U4 U5 U6 R1 R4 R7 "
        "D3 R2 R3 D2 R5 R6 D1 R8 R9 "
        "F3 F6 F9 F2 F5 F8 F1 F4 F7 "
        "L3 L6 L9 D4 D5 D6 D7 D8 D9 "
        "L1 L2 U9 L4 L5 U8 L7 L8 U7 "
        "B1 B2 B3 B4 B5 B6 B7 B8 B9"
    ),
    "D": (
        "U1 U2 U3 U4 U5 U6 U7 U8 U9 "
        "R1 R2 R3 R4 R5 R6 B7 B8 B9 "
        "F1 F2 F3 F4 F5 F6 R7 R8 R9 "
        "D3 D6 D9 D2 D5 D8 D1 D4 D7 "
        "L1 L2 L3 L4 L5 L6 F7 F8 F9 "
        "B1 B2 B3 B4 B5 B6 L7 L8 L9"
    ),
    "L": (
        "F1 U2 U3 F4 U5 U6 F7 U8 U9 "
        "R1 R2 R3 R4 R5 R6 R7 R8 R9 "
        "D1 F2 F3 D4 F5 F6 D7 F8 F9 "
        "B9 D2 D3 B6 D5 D6 B3 D8 D9 "
        "L3 L6 L9 L2 L5 L8 L1 L4 L7 "
        "B1 B2 U7 B4 B5 U4 B7 B8 U1"
    ),
    "B": (
        "L7 L4 L1 U4 U5 U6 U7 U8 U9 "
        "R1 R2 U1 R4 R5 U2 R7 R8 U3 "
        "F1 F2 F3 F4 F5 F6 F7 F8 F9 "
        "D1 D2 D3 D4 D5 D6 R9 R6 R3 "
        "D7 L2 L3 D8 L5 L6 D9 L8 L9 "
        "B3 B6 B9 B2 B5 B8 B1 B4 B7"
    ),
}

#: ``KOCIEMBA_FACE_MOVES["F"][i]`` is the facelet that the sticker at facelet
#: ``i`` moves to when ``F`` is applied.
KOCIEMBA_FACE_MOVES: Final[dict[str, tuple[int, ...]]] = {
    name: tuple(facelet_index_of_name(token) for token in raw.split())
    for name, raw in _KOCIEMBA_RAW.items()
}

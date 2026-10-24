"""Cubie level view of the cube: corner and edge permutations plus orientations.

The facelet representation is what a human sees, but the algebra of the cube is
far clearer on the cubie level: eight corners and twelve edges, each with a
position and an orientation.  This module provides the standard projection using
Kociemba's corner and edge facelet mappings, together with the three invariants
that decide whether a state is solvable at all:

* the sum of the eight corner orientations is divisible by three,
* the sum of the twelve edge orientations is divisible by two,
* the corner and edge permutations have the same parity.

The projection is used by the solvers (the cross and F2L searches reason about
pieces, not stickers) and by the validity checks that protect the engine from
impossible states such as a single twisted corner.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.facelets import (
    FACE_ORDER,
    FACELET_COUNT,
    SOLVED_FACELETS,
    facelet_index,
    facelet_name,
    index_of_name,
)
from rubiks_cfop.cube.moves import (
    Move,
    MoveKind,
    compose,
    conjugate,
    get_move,
    invert_permutation,
    normalized_facelets,
)
from rubiks_cfop.errors import InvalidMoveError, InvalidStateError, UnsolvableStateError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "CORNER_FACELETS",
    "CORNER_NAMES",
    "EDGE_FACELETS",
    "EDGE_NAMES",
    "CubieCube",
    "corner_position",
    "cubie_permutation",
    "edge_position",
    "move_cubie",
]

#: Corner cubie names, in Kociemba order.
CORNER_NAMES: Final[tuple[str, ...]] = (
    "URF",
    "UFL",
    "ULB",
    "UBR",
    "DFR",
    "DLF",
    "DBL",
    "DRB",
)

#: The three facelets of each corner position, in Kociemba order.
CORNER_FACELETS: Final[tuple[tuple[str, str, str], ...]] = (
    ("U9", "R1", "F3"),
    ("U7", "F1", "L3"),
    ("U1", "L1", "B3"),
    ("U3", "B1", "R3"),
    ("D3", "F9", "R7"),
    ("D1", "L9", "F7"),
    ("D7", "B9", "L7"),
    ("D9", "R9", "B7"),
)

#: The colours of each corner cubie, in the same order as its facelets.
CORNER_COLORS: Final[tuple[tuple[str, str, str], ...]] = (
    ("U", "R", "F"),
    ("U", "F", "L"),
    ("U", "L", "B"),
    ("U", "B", "R"),
    ("D", "F", "R"),
    ("D", "L", "F"),
    ("D", "B", "L"),
    ("D", "R", "B"),
)

#: Edge cubie names, in Kociemba order.
EDGE_NAMES: Final[tuple[str, ...]] = (
    "UR",
    "UF",
    "UL",
    "UB",
    "DR",
    "DF",
    "DL",
    "DB",
    "FR",
    "FL",
    "BL",
    "BR",
)

#: The two facelets of each edge position, in Kociemba order.
EDGE_FACELETS: Final[tuple[tuple[str, str], ...]] = (
    ("U6", "R2"),
    ("U8", "F2"),
    ("U4", "L2"),
    ("U2", "B2"),
    ("D6", "R8"),
    ("D2", "F8"),
    ("D4", "L8"),
    ("D8", "B8"),
    ("F6", "R4"),
    ("F4", "L6"),
    ("B6", "L4"),
    ("B4", "R6"),
)

#: The colours of each edge cubie, in the same order as its facelets.
EDGE_COLORS: Final[tuple[tuple[str, str], ...]] = (
    ("U", "R"),
    ("U", "F"),
    ("U", "L"),
    ("U", "B"),
    ("D", "R"),
    ("D", "F"),
    ("D", "L"),
    ("D", "B"),
    ("F", "R"),
    ("F", "L"),
    ("B", "L"),
    ("B", "R"),
)

CORNER_COUNT: Final = len(CORNER_NAMES)
EDGE_COUNT: Final = len(EDGE_NAMES)

_CORNER_FACELET_INDEX: Final[tuple[tuple[int, int, int], ...]] = tuple(
    (index_of_name(a), index_of_name(b), index_of_name(c)) for a, b, c in CORNER_FACELETS
)
_EDGE_FACELET_INDEX: Final[tuple[tuple[int, int], ...]] = tuple(
    (index_of_name(a), index_of_name(b)) for a, b in EDGE_FACELETS
)

_UP_DOWN_COLORS: Final[frozenset[str]] = frozenset({"U", "D"})


def _permutation_parity(permutation: tuple[int, ...]) -> int:
    """Return 0 for an even permutation and 1 for an odd one."""
    inversions = 0
    for i, first in enumerate(permutation):
        for second in permutation[i + 1 :]:
            inversions += first > second
    return inversions % 2


def corner_position(name: str) -> int:
    """Return the index of a corner position given its name, for example ``URF``.

    Raises:
        ValueError: If ``name`` is not a corner name.
    """
    try:
        return CORNER_NAMES.index(name.strip().upper())
    except ValueError as exc:
        raise ValueError(f"not a corner position: {name!r}") from exc


def edge_position(name: str) -> int:
    """Return the index of an edge position given its name, for example ``UF``.

    Raises:
        ValueError: If ``name`` is not an edge name.
    """
    try:
        return EDGE_NAMES.index(name.strip().upper())
    except ValueError as exc:
        raise ValueError(f"not an edge position: {name!r}") from exc


@dataclass(frozen=True, slots=True)
class CubieCube:
    """A cube state as corner and edge permutations with orientations.

    Attributes:
        cp: ``cp[i]`` is the corner cubie at corner position ``i``.
        co: ``co[i]`` is the orientation of that corner, 0, 1 or 2.
        ep: ``ep[i]`` is the edge cubie at edge position ``i``.
        eo: ``eo[i]`` is the orientation of that edge, 0 or 1.
    """

    cp: tuple[int, ...]
    co: tuple[int, ...]
    ep: tuple[int, ...]
    eo: tuple[int, ...]

    @classmethod
    def solved(cls) -> CubieCube:
        """Return the solved cube."""
        return cls(
            cp=tuple(range(CORNER_COUNT)),
            co=(0,) * CORNER_COUNT,
            ep=tuple(range(EDGE_COUNT)),
            eo=(0,) * EDGE_COUNT,
        )

    @classmethod
    def from_facelets(cls, facelets: str) -> CubieCube:
        """Project a facelet string onto the cubie level.

        Any whole cube rotation is undone first, so a rotated state projects onto
        the same cubie state as its unrotated equivalent: the projection describes
        the physical cube relative to its own centres, not the way it is held.

        To project in the *display* frame instead -- for example after reorienting
        the cube on purpose -- relabel the colours first with
        :func:`~rubiks_cfop.cube.facelets.canonicalize_colors`.

        Raises:
            InvalidStateError: If the facelets do not describe a cube, for
                example a corner without any up or down sticker, or a piece
                combination that does not exist.
        """
        facelets = normalized_facelets(facelets)
        cp: list[int] = []
        co: list[int] = []
        for position, facelets_of_corner in enumerate(_CORNER_FACELET_INDEX):
            orientation = _corner_orientation(facelets, facelets_of_corner, position)
            first = facelets[facelets_of_corner[(orientation + 1) % 3]]
            second = facelets[facelets_of_corner[(orientation + 2) % 3]]
            cp.append(_find_corner(first, second, position))
            co.append(orientation)

        ep: list[int] = []
        eo: list[int] = []
        for position, facelets_of_edge in enumerate(_EDGE_FACELET_INDEX):
            cubie, orientation = _find_edge(
                facelets[facelets_of_edge[0]],
                facelets[facelets_of_edge[1]],
                position,
            )
            ep.append(cubie)
            eo.append(orientation)

        return cls(cp=tuple(cp), co=tuple(co), ep=tuple(ep), eo=tuple(eo))

    def to_facelets(self) -> str:
        """Render this cubie state as a Kociemba facelet string."""
        facelets = ["?"] * FACELET_COUNT
        for face in FACE_ORDER:
            facelets[facelet_index(face, 5)] = face.value
        for position, facelets_of_corner in enumerate(_CORNER_FACELET_INDEX):
            cubie = self.cp[position]
            orientation = self.co[position]
            for index in range(3):
                target = (index + orientation) % 3
                facelets[facelets_of_corner[target]] = CORNER_COLORS[cubie][index]
        for position, facelets_of_edge in enumerate(_EDGE_FACELET_INDEX):
            cubie = self.ep[position]
            orientation = self.eo[position]
            for index in range(2):
                target = (index + orientation) % 2
                facelets[facelets_of_edge[target]] = EDGE_COLORS[cubie][index]
        return "".join(facelets)

    def apply(self, move: Move | str) -> CubieCube:
        """Return this state after applying one move.

        Whole cube rotations leave the cubie state unchanged, because rotating the
        puzzle does not rearrange any piece relative to its own centres.

        Raises:
            InvalidMoveError: For wide and slice moves.  Those move the centres, so
                they are not elements of the cubie group: the frame they leave
                behind is part of their meaning.  Apply them to a
                :class:`~rubiks_cfop.cube.cube.Cube` instead, which keeps the full
                display state.
        """
        resolved = get_move(move) if isinstance(move, str) else move
        if resolved.kind is MoveKind.ROTATION:
            return self
        if resolved.kind in {MoveKind.WIDE, MoveKind.SLICE}:
            raise InvalidMoveError(
                "wide and slice moves are not cubie group elements",
                move=resolved.name,
                hint="apply them to a Cube, which tracks the display orientation",
            )
        return _compose(self, cubie_permutation(resolved.carried_to))

    def apply_moves(self, moves: Iterable[Move | str]) -> CubieCube:
        """Return this state after applying a sequence of moves.

        Rotations are interpreted as changes of the frame that following moves are
        named in, so ``y R y'`` is the physical turn ``B``.

        Raises:
            InvalidMoveError: For wide and slice moves, as in :meth:`apply`.
        """
        state = self
        frame: tuple[int, ...] | None = None
        for move in moves:
            resolved = get_move(move) if isinstance(move, str) else move
            if resolved.kind is MoveKind.ROTATION:
                frame = (
                    resolved.carried_to if frame is None else compose(frame, resolved.carried_to)
                )
                continue
            if resolved.kind in {MoveKind.WIDE, MoveKind.SLICE}:
                raise InvalidMoveError(
                    "wide and slice moves are not cubie group elements",
                    move=resolved.name,
                    hint="apply them to a Cube, which tracks the display orientation",
                )
            permutation = (
                resolved.carried_to if frame is None else conjugate(resolved.carried_to, frame)
            )
            state = _compose(state, cubie_permutation(permutation))
        return state

    def is_solved(self) -> bool:
        """Return whether every piece is home and unoriented."""
        return self == CubieCube.solved()

    def is_solvable(self) -> bool:
        """Return whether this state satisfies the cube's invariants."""
        try:
            self.validate()
        except (InvalidStateError, UnsolvableStateError):
            return False
        return True

    def validate(self) -> None:
        """Check the structural and algebraic invariants of a cube state.

        Raises:
            InvalidStateError: If the permutations or orientations are malformed.
            UnsolvableStateError: If the state violates one of the three
                invariants (corner twist, edge flip, permutation parity).
        """
        if sorted(self.cp) != list(range(CORNER_COUNT)):
            raise InvalidStateError("corner permutation is not a permutation", cp=list(self.cp))
        if sorted(self.ep) != list(range(EDGE_COUNT)):
            raise InvalidStateError("edge permutation is not a permutation", ep=list(self.ep))
        if any(orientation not in (0, 1, 2) for orientation in self.co):
            raise InvalidStateError("corner orientations must be 0, 1 or 2", co=list(self.co))
        if any(orientation not in (0, 1) for orientation in self.eo):
            raise InvalidStateError("edge orientations must be 0 or 1", eo=list(self.eo))
        twist = sum(self.co) % 3
        if twist:
            raise UnsolvableStateError(
                "the corner orientation sum must be divisible by three",
                twist=twist,
            )
        flip = sum(self.eo) % 2
        if flip:
            raise UnsolvableStateError("the edge orientation sum must be even", flip=flip)
        if _permutation_parity(self.cp) != _permutation_parity(self.ep):
            raise UnsolvableStateError("corner and edge permutations must have the same parity")


def _corner_orientation(
    facelets: str,
    facelets_of_corner: tuple[int, int, int],
    position: int,
) -> int:
    """Return the index of the facelet carrying the corner's up or down colour."""
    for orientation in range(3):
        if facelets[facelets_of_corner[orientation]] in _UP_DOWN_COLORS:
            return orientation
    raise InvalidStateError(
        "corner has no up or down sticker",
        corner=CORNER_NAMES[position],
        facelets=[facelet_name(index) for index in facelets_of_corner],
    )


def _find_corner(first: str, second: str, position: int) -> int:
    """Return the corner cubie whose two side colours match, or raise."""
    for cubie, colors in enumerate(CORNER_COLORS):
        if first == colors[1] and second == colors[2]:
            return cubie
    raise InvalidStateError(
        "unknown corner piece",
        corner=CORNER_NAMES[position],
        colors=[first, second],
    )


def _find_edge(first: str, second: str, position: int) -> tuple[int, int]:
    """Return the edge cubie and orientation matching two sticker colours."""
    for cubie, colors in enumerate(EDGE_COLORS):
        if first == colors[0] and second == colors[1]:
            return cubie, 0
        if first == colors[1] and second == colors[0]:
            return cubie, 1
    raise InvalidStateError(
        "unknown edge piece",
        edge=EDGE_NAMES[position],
        colors=[first, second],
    )


def _compose(first: CubieCube, second: CubieCube) -> CubieCube:
    """Return the state that results from applying ``first`` and then ``second``.

    Follows Kociemba's ``CornMult``/``EdgeMult``: the piece at a position is
    looked up in ``first`` after being located in ``second``, and orientations
    add modulo three for corners and modulo two for edges.
    """
    return CubieCube(
        cp=tuple(first.cp[second.cp[index]] for index in range(CORNER_COUNT)),
        co=tuple(
            (first.co[second.cp[index]] + second.co[index]) % 3 for index in range(CORNER_COUNT)
        ),
        ep=tuple(first.ep[second.ep[index]] for index in range(EDGE_COUNT)),
        eo=tuple(
            (first.eo[second.ep[index]] + second.eo[index]) % 2 for index in range(EDGE_COUNT)
        ),
    )


@cache
def cubie_permutation(permutation: tuple[int, ...]) -> CubieCube:
    """Return the cubie state of a facelet permutation applied to a solved cube."""
    inverse = invert_permutation(permutation)
    return CubieCube.from_facelets("".join(SOLVED_FACELETS[index] for index in inverse))


def move_cubie(move: Move) -> CubieCube:
    """Return the cubie level state of applying ``move`` to a solved cube."""
    return cubie_permutation(move.carried_to)

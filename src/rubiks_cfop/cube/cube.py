"""Immutable cube state in Kociemba facelet representation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.facelets import (
    FACE_COLOR,
    FACE_ORDER,
    SOLVED_FACELETS,
    Color,
    Face,
    centers_are_canonical,
    face_facelets,
    index_of_name,
    validate_facelets,
)
from rubiks_cfop.cube.moves import Move, get_move, normalized_facelets
from rubiks_cfop.cube.notation import parse_moves, parse_scramble

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = ["Cube"]


@dataclass(frozen=True, slots=True)
class Cube:
    """An immutable cube state.

    The state is the 54 character Kociemba facelet string.  Construction
    validates the string, so an instance is always well formed; whether it is
    *solvable* is a separate question answered by :meth:`is_solvable`.

    The class is a value object: it is hashable, comparable and never mutated,
    which makes it safe to share between threads and to send to a GUI.
    """

    facelets: str

    def __post_init__(self) -> None:
        """Validate and normalize the facelet string."""
        normalized = validate_facelets(self.facelets)
        if normalized != self.facelets:
            object.__setattr__(self, "facelets", normalized)

    @classmethod
    def solved(cls) -> Cube:
        """Return the solved cube."""
        return cls(SOLVED_FACELETS)

    @classmethod
    def from_facelets(cls, text: str) -> Cube:
        """Build a cube from a facelet string, ignoring whitespace and case.

        Raises:
            InvalidStateError: If the string is not a well formed cube state.
        """
        return cls(text)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Cube:
        """Build a cube from the output of :meth:`to_dict`."""
        return cls(str(payload["facelets"]))

    def apply(self, move: Move | str) -> Cube:
        """Return the cube after applying one move.

        Args:
            move: A :class:`~rubiks_cfop.cube.moves.Move` or a canonical name
                such as ``"R"``, ``"R2"``, ``"R'"`` or ``"Rw"``.

        Raises:
            InvalidMoveError: If a name is given that is not a canonical move.
        """
        return Cube(self._resolved(move).apply_to(self.facelets))

    def apply_moves(self, moves: Iterable[Move | str]) -> Cube:
        """Return the cube after applying a sequence of moves."""
        facelets = self.facelets
        for move in moves:
            facelets = self._resolved(move).apply_to(facelets)
        return Cube(facelets)

    def apply_sequence(self, text: str) -> Cube:
        """Return the cube after applying a move sequence in WCA notation.

        Raises:
            NotationError: If ``text`` is not valid notation.
        """
        return self.apply_moves(parse_moves(text))

    def apply_scramble(self, text: str) -> Cube:
        """Return the cube after applying a scramble, which the user may supply.

        Raises:
            NotationError: If ``text`` is not valid notation.
        """
        return self.apply_moves(parse_scramble(text))

    def is_solved(self) -> bool:
        """Return whether every face shows a single color.

        A cube that has only been rotated counts as solved, because rotating the
        whole cube does not change the puzzle.
        """
        return all(len(set(self.face_facelets(face))) == 1 for face in FACE_ORDER)

    def normalized(self) -> Cube:
        """Return the same physical cube with its center colors in place.

        Whole cube rotations permute which colors appear on which face.  This
        returns the canonical description of the same physical cube, obtained by
        undoing that rotation, which is what the cubie level projection and the
        solvers work with.

        Raises:
            InvalidStateError: If the centers are not a valid rotation.
        """
        return Cube(normalized_facelets(self.facelets))

    def is_canonical(self) -> bool:
        """Return whether no whole cube rotation is reflected in the centers."""
        return centers_are_canonical(self.facelets)

    def is_solvable(self) -> bool:
        """Return whether this state satisfies the cube's algebraic invariants."""
        return self.cubie().is_solvable()

    def facelet(self, name: str) -> str:
        """Return the letter of a named facelet, for example ``"U1"``."""
        return self.facelets[index_of_name(name)]

    def face_facelets(self, face: Face | str) -> str:
        """Return the nine facelets of one face, in reading order."""
        return face_facelets(self.facelets, face)

    def colors(self) -> tuple[Color, ...]:
        """Return the 54 facelet colors, in Kociemba facelet order."""
        return tuple(FACE_COLOR[Face(letter)] for letter in self.facelets)

    def cubie(self) -> CubieCube:
        """Return the cubie level view of this state."""
        return CubieCube.from_facelets(self.facelets)

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation of this state."""
        return {"facelets": self.facelets}

    def __str__(self) -> str:
        """Return the facelet string."""
        return self.facelets

    @staticmethod
    def _resolved(move: Move | str) -> Move:
        """Return a :class:`Move` for a move or canonical move name."""
        return get_move(move) if isinstance(move, str) else move

"""The result of scramble generation, shared by all scramble styles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import SOLVED_FACELETS
from rubiks_cfop.cube.notation import format_moves, parse_moves

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rubiks_cfop.cube.moves import Move

__all__ = ["Scramble", "ScrambleStyle"]


class ScrambleStyle(StrEnum):
    """How a scramble sequence is produced."""

    #: A filtered sequence of random face turns.
    RANDOM_MOVE = "random-move"
    #: A uniformly random cube state, solved to obtain the scramble (WCA 4b3).
    RANDOM_STATE = "random-state"


@dataclass(frozen=True, slots=True)
class Scramble:
    """A scramble sequence and the state it produces.

    Attributes:
        moves: The moves, in order.
        style: How the sequence was generated.
        seed: The seed that reproduces this exact scramble.
        state: The cube state after applying the scramble to a solved cube.
    """

    moves: tuple[Move, ...]
    style: ScrambleStyle
    seed: int
    state: Cube

    @property
    def text(self) -> str:
        """Return the scramble in canonical WCA notation."""
        return format_moves(self.moves)

    @property
    def length(self) -> int:
        """Return the number of moves."""
        return len(self.moves)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "text": self.text,
            "moves": [move.name for move in self.moves],
            "style": self.style.value,
            "seed": self.seed,
            "facelets": self.state.facelets,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Scramble:
        """Rebuild a scramble from :meth:`to_dict` output."""
        raw_moves = payload["moves"]
        text = " ".join(raw_moves) if isinstance(raw_moves, list) else str(raw_moves)
        return cls(
            moves=parse_moves(text),
            style=ScrambleStyle(str(payload["style"])),
            seed=int(str(payload["seed"])),
            state=Cube.from_facelets(str(payload["facelets"])),
        )

    @classmethod
    def from_moves(
        cls,
        moves: tuple[Move, ...],
        *,
        style: ScrambleStyle,
        seed: int,
    ) -> Scramble:
        """Build a scramble from moves, deriving the resulting state."""
        state = Cube.from_facelets(SOLVED_FACELETS).apply_moves(moves)
        return cls(moves=moves, style=style, seed=seed, state=state)

    def __str__(self) -> str:
        """Return the scramble in canonical notation."""
        return self.text

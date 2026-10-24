"""Parsing and formatting of move sequences in WCA notation.

The grammar accepted by :func:`parse_moves` is deliberately wider than the
canonical output of :func:`format_moves`:

* face turns ``U D L R F B``, wide turns ``Uw Dw Lw Rw Fw Bw`` and rotations
  ``x y z``, each with the suffix ``2`` (half turn) or ``'`` (counter clockwise),
  as defined by WCA Regulation 12a;
* slice turns ``M E S`` as a documented extension, because many published OLL and
  PLL algorithms use them;
* ``2Rw`` as an alias for ``Rw`` (Regulation 12a2+: ``n`` defaults to 2);
* lower case ``r l u d f b`` as an alias for the wide turns and ``m e s`` for the
  slice turns, as used by older algorithm listings;
* ``2'`` and ``'2`` as a tolerated spelling of the half turn ``2``;
* arbitrary whitespace, including newlines and tabs, between moves.

Anything else, including the invalid layer prefixes ``1Rw`` and ``3Rw`` on a
3x3x3, raises :class:`~rubiks_cfop.errors.NotationError` with the offending token
and its index, so a GUI can point at the exact position.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.moves import Move, get_move
from rubiks_cfop.errors import InvalidMoveError, NotationError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "format_moves",
    "is_valid_token",
    "normalize_sequence",
    "parse_moves",
    "parse_scramble",
]

_TOKEN_RE: Final = re.compile(
    r"(?P<prefix>\d*)"
    r"(?P<base>[URFDLB][wW]?|[MESmes]|[xyz]|[rludfb])"
    r"(?P<suffix>2'|'2|2|')?"
)

_WIDE_ALIASES: Final[dict[str, str]] = {
    "r": "Rw",
    "l": "Lw",
    "u": "Uw",
    "d": "Dw",
    "f": "Fw",
    "b": "Bw",
}

_SLICE_ALIASES: Final[dict[str, str]] = {"m": "M", "e": "E", "s": "S"}

_SUFFIX_ALIASES: Final[dict[str, str]] = {"2'": "2", "'2": "2", "2": "2", "'": "'", "": ""}

#: A wide move base such as ``Rw`` has a face letter and a ``w``.
_WIDE_BASE_LENGTH: Final = 2


def _canonical_base(base: str) -> str:
    """Return the canonical spelling of a move base, or raise ``ValueError``."""
    if base in _WIDE_ALIASES:
        return _WIDE_ALIASES[base]
    if base in _SLICE_ALIASES:
        return _SLICE_ALIASES[base]
    if base[0] in "URFDLB":
        face = base[0]
        return f"{face}w" if base[-1] in "wW" and len(base) == _WIDE_BASE_LENGTH else face
    return base


def _token_to_name(token: str) -> str:
    """Convert one notation token into a canonical move name.

    Raises:
        ValueError: If the token is not valid WCA notation for a 3x3x3 cube.
    """
    match = _TOKEN_RE.fullmatch(token)
    if match is None:
        msg = "not WCA move notation"
        raise ValueError(msg)

    prefix = match.group("prefix")
    raw_base = match.group("base")
    base = _canonical_base(raw_base)
    suffix = _SUFFIX_ALIASES[match.group("suffix") or ""]

    is_wide = base.endswith("w")
    if prefix:
        if prefix != "2":
            msg = f"layer prefix {prefix!r} is invalid on a 3x3x3 cube"
            raise ValueError(msg)
        if not is_wide:
            msg = f"layer prefix {prefix!r} is only valid for wide moves such as {prefix}{base}w"
            raise ValueError(msg)

    return f"{base}{suffix}"


def is_valid_token(token: str) -> bool:
    """Return whether ``token`` is a single move in accepted notation."""
    try:
        _token_to_name(token)
    except ValueError:
        return False
    return True


def parse_moves(text: str) -> tuple[Move, ...]:
    """Parse a whitespace separated move sequence.

    Args:
        text: The sequence, for example ``"R U R' U' F2"``.  An empty or blank
            string yields an empty sequence.

    Returns:
        The parsed moves.

    Raises:
        NotationError: If any token is not valid notation, carrying the offending
            token and its zero-based index.
    """
    moves: list[Move] = []
    for index, token in enumerate(text.split()):
        try:
            moves.append(get_move(_token_to_name(token)))
        except ValueError as exc:
            raise NotationError(str(exc), token=token, index=index) from exc
        except InvalidMoveError as exc:  # pragma: no cover - grammar guarantees validity
            raise NotationError("unknown move", token=token, index=index) from exc
    return tuple(moves)


def parse_scramble(text: str) -> tuple[Move, ...]:
    """Parse a scramble sequence, including one supplied by a user.

    This is :func:`parse_moves` with a name that matches its use: scrambles come
    from WCA generators, from other tools or from the user.

    Raises:
        NotationError: If any token is not valid notation.
    """
    return parse_moves(text)


def format_moves(moves: Iterable[Move]) -> str:
    """Format moves in canonical notation, separated by single spaces."""
    return " ".join(move.name for move in moves)


def normalize_sequence(text: str) -> str:
    """Return ``text`` rewritten in canonical notation.

    Raises:
        NotationError: If any token is not valid notation.
    """
    return format_moves(parse_moves(text))

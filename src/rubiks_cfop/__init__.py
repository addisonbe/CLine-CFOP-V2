"""Headless engine for WCA scramble generation and CFOP solving of the 3x3x3 cube.

The package is deliberately free of I/O: it never prints, never reads ``sys.argv``
and never inspects the environment, so the same code can be embedded in a CLI, a
desktop GUI or a web service.  Everything the engine produces is a structured,
JSON-serializable value; formatting is the caller's job.

Public API
----------
The supported surface is re-exported here and documented in ``docs/api.md``.
Anything not listed in :data:`__all__` is an implementation detail.

Design constraints (enforced by tests)
--------------------------------------
* no output on ``stdout``/``stderr`` and no environment access,
* no third-party runtime dependencies,
* no mutable global state; solvers are reusable and thread-safe,
* imports stay cheap so that a GUI can start quickly.
"""

from __future__ import annotations

from rubiks_cfop.cube import (
    MOVES,
    SOLVED_FACELETS,
    Color,
    Cube,
    CubieCube,
    Face,
    Move,
    MoveKind,
    format_moves,
    get_move,
    invert,
    is_valid_token,
    normalize_sequence,
    parse_moves,
    parse_scramble,
    validate_facelets,
)
from rubiks_cfop.errors import (
    CancelledError,
    InvalidMoveError,
    InvalidStateError,
    NotationError,
    RubiksError,
    SolveTimeoutError,
    UnsolvableStateError,
)

__version__ = "0.1.0"

__all__ = [
    "MOVES",
    "SOLVED_FACELETS",
    "CancelledError",
    "Color",
    "Cube",
    "CubieCube",
    "Face",
    "InvalidMoveError",
    "InvalidStateError",
    "Move",
    "MoveKind",
    "NotationError",
    "RubiksError",
    "SolveTimeoutError",
    "UnsolvableStateError",
    "__version__",
    "format_moves",
    "get_move",
    "invert",
    "is_valid_token",
    "normalize_sequence",
    "parse_moves",
    "parse_scramble",
    "validate_facelets",
]

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

from rubiks_cfop.cancel import CancelToken
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
    SearchLimitError,
    SolveTimeoutError,
    UnsolvableStateError,
)
from rubiks_cfop.render import (
    DEFAULT_PALETTE,
    NetLayout,
    net_layout,
    render_ansi,
    render_emoji,
    render_letters,
)
from rubiks_cfop.scramble import (
    Scramble,
    ScrambleStyle,
    generate_scramble,
    generate_scrambles,
)
from rubiks_cfop.solver import SearchLimits, preload, solve
from rubiks_cfop.solver.cfop import (
    CrossOption,
    Solution,
    Stage,
    cross_options,
    solve_cube,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_PALETTE",
    "MOVES",
    "SOLVED_FACELETS",
    "CancelToken",
    "CancelledError",
    "Color",
    "CrossOption",
    "Cube",
    "CubieCube",
    "Face",
    "InvalidMoveError",
    "InvalidStateError",
    "Move",
    "MoveKind",
    "NetLayout",
    "NotationError",
    "RubiksError",
    "Scramble",
    "ScrambleStyle",
    "SearchLimitError",
    "SearchLimits",
    "Solution",
    "SolveTimeoutError",
    "Stage",
    "UnsolvableStateError",
    "__version__",
    "cross_options",
    "format_moves",
    "generate_scramble",
    "generate_scrambles",
    "get_move",
    "invert",
    "is_valid_token",
    "net_layout",
    "normalize_sequence",
    "parse_moves",
    "parse_scramble",
    "preload",
    "render_ansi",
    "render_emoji",
    "render_letters",
    "solve",
    "solve_cube",
    "validate_facelets",
]

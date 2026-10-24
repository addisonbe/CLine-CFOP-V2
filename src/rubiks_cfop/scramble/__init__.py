"""Scramble generation.

Two generators are provided, selected by :class:`ScrambleStyle`:

``random-state`` (default)
    A uniformly random cube state which is then solved to produce the scramble,
    which is exactly what WCA Regulation 4b3 asks for ("a random state from all
    states that require at least 2 moves to solve").  The first call builds the
    solver's tables, which takes a few seconds; :func:`~rubiks_cfop.solver.preload`
    lets a GUI pay that cost up front on a background thread.

``random-move``
    A filtered sequence of random face turns.  Instant, and what most tools mean by
    "a scramble string", but not what Regulation 4b3 requires for the 3x3x3.

Both are deterministic for a given seed, and the seed is always recorded in the
result so a scramble can be reproduced or shared.
"""

from __future__ import annotations

from rubiks_cfop.scramble.random_move import random_move_scramble, random_move_scrambles
from rubiks_cfop.scramble.random_state import random_state_scramble, random_state_scrambles
from rubiks_cfop.scramble.scramble import Scramble, ScrambleStyle

__all__ = [
    "Scramble",
    "ScrambleStyle",
    "generate_scramble",
    "generate_scrambles",
    "random_move_scramble",
    "random_move_scrambles",
    "random_state_scramble",
    "random_state_scrambles",
]


def generate_scramble(
    *,
    style: ScrambleStyle | str = ScrambleStyle.RANDOM_STATE,
    seed: int | None = None,
    length: int | None = None,
) -> Scramble:
    """Generate one scramble.

    Args:
        style: ``"random-state"`` (default) or ``"random-move"``.
        seed: Seed for reproducible output.  When omitted, a fresh seed is drawn
            and recorded in the result.
        length: Exact number of moves for ``random-move``; an upper bound for
            ``random-state``.

    Returns:
        The scramble, together with the state it produces.

    Raises:
        ValueError: If ``style`` is unknown.
    """
    resolved = ScrambleStyle(style)
    if resolved is ScrambleStyle.RANDOM_MOVE:
        return random_move_scramble(seed=seed, length=length)
    return random_state_scramble(seed=seed, length=length)


def generate_scrambles(
    count: int,
    *,
    style: ScrambleStyle | str = ScrambleStyle.RANDOM_STATE,
    seed: int | None = None,
    length: int | None = None,
) -> list[Scramble]:
    """Generate ``count`` independent scrambles.

    Args:
        count: How many scrambles to produce.
        style: ``"random-state"`` (default) or ``"random-move"``.
        seed: Seed for the sequence; each scramble gets its own derived seed.
        length: Exact number of moves for ``random-move``; an upper bound for
            ``random-state``.

    Returns:
        The scrambles, in order.

    Raises:
        ValueError: If ``count`` is negative or ``style`` is unknown.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    resolved = ScrambleStyle(style)
    if resolved is ScrambleStyle.RANDOM_MOVE:
        return random_move_scrambles(count, seed=seed, length=length)
    return random_state_scrambles(count, seed=seed, length=length)

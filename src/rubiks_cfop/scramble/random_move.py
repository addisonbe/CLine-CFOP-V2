"""The random-move scramble generator.

Moves are drawn uniformly from the 18 face turns, then filtered the way scramble
programs filter them: no two consecutive turns of the same face, and no three
consecutive turns on the same axis (so ``R L R`` is rejected).  The result is a
scramble in WCA notation, but note that WCA Regulation 4b3 requires *random-state*
scrambles for the 3x3x3 -- see :mod:`rubiks_cfop.scramble.random_state`.  The
random-move generator remains useful for practice scrambles and for Fewest Moves
style sequences, where Regulation 4b3e allows it.
"""

from __future__ import annotations

import random
from typing import Final

from rubiks_cfop.cube.facelets import FACE_ORDER, Face
from rubiks_cfop.cube.moves import get_move
from rubiks_cfop.scramble.scramble import Scramble, ScrambleStyle

__all__ = ["DEFAULT_LENGTH", "random_move_scramble", "random_move_scrambles"]

#: Default length of a random-move scramble, in moves.
DEFAULT_LENGTH: Final = 20

#: The 18 face turns a scramble is built from.
FACE_TURNS: Final[tuple[str, ...]] = tuple(
    f"{face.value}{suffix}" for face in FACE_ORDER for suffix in ("", "2", "'")
)

#: How many trailing moves to inspect when rejecting a same-axis run.
_AXIS_RUN_WINDOW: Final = 2

#: Faces grouped by axis, used for the "no three turns on one axis" filter.
_AXIS_FACES: Final[tuple[frozenset[Face], ...]] = (
    frozenset({Face.R, Face.L}),
    frozenset({Face.U, Face.D}),
    frozenset({Face.F, Face.B}),
)


def _axis_of(face: Face) -> int:
    """Return the index of the axis a face belongs to."""
    for index, faces in enumerate(_AXIS_FACES):
        if face in faces:
            return index
    raise AssertionError(f"unknown face {face!r}")  # pragma: no cover - exhaustive


def _is_allowed(sequence: list[str], candidate: str) -> bool:
    """Return whether ``candidate`` may follow ``sequence``."""
    face = get_move(candidate).face
    if face is None:  # pragma: no cover - face turns always have a face
        return False
    if sequence:
        last_face = get_move(sequence[-1]).face
        if last_face is face:
            return False
        if len(sequence) >= _AXIS_RUN_WINDOW:
            before_face = get_move(sequence[-2]).face
            axis = _axis_of(face)
            if (
                before_face is not None
                and _axis_of(before_face) == axis
                and last_face is not None
                and _axis_of(last_face) == axis
            ):
                return False
    return True


def random_move_scramble(*, seed: int | None = None, length: int | None = None) -> Scramble:
    """Generate a filtered random-move scramble.

    Args:
        seed: Seed for reproducible output; a fresh seed is drawn when omitted.
        length: Number of moves; defaults to :data:`DEFAULT_LENGTH`.

    Returns:
        The scramble and the state it produces.

    Raises:
        ValueError: If ``length`` is not positive.
    """
    moves_count = DEFAULT_LENGTH if length is None else length
    if moves_count < 1:
        raise ValueError(f"length must be positive, got {moves_count}")

    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    # A seeded Mersenne Twister is exactly what a reproducible scramble needs;
    # unpredictability comes from the 32 bit seed above, not from the generator.
    rng = random.Random(seed)  # noqa: S311

    names: list[str] = []
    while len(names) < moves_count:
        candidate = rng.choice(FACE_TURNS)
        if _is_allowed(names, candidate):
            names.append(candidate)

    moves = tuple(get_move(name) for name in names)
    return Scramble.from_moves(moves, style=ScrambleStyle.RANDOM_MOVE, seed=seed)


def random_move_scrambles(
    count: int,
    *,
    seed: int | None = None,
    length: int | None = None,
) -> list[Scramble]:
    """Generate ``count`` independent random-move scrambles.

    Args:
        count: How many scrambles to produce.
        seed: Seed for the whole sequence; each scramble derives its own seed.
        length: Number of moves per scramble.

    Returns:
        The scrambles, in order.

    Raises:
        ValueError: If ``count`` is negative or ``length`` is not positive.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)  # noqa: S311 - reproducible by design, see above
    return [random_move_scramble(seed=rng.randrange(2**32), length=length) for _ in range(count)]

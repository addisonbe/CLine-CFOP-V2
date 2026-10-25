"""Random-state scrambles, as required by WCA Regulation 4b3.

Regulation 4b3 asks an official scramble program to "produce a random state from
all states that require at least 2 moves to solve (equal probability for each
state)".  A random-state scramble is therefore built in two steps:

1. draw a uniformly random solvable cube state;
2. solve that state with the two-phase solver, and hand back the *inverse* of the
   solution, which is the sequence that turns a solved cube into exactly that
   state.

The result is a sequence of about 22 moves, in the same ballpark as the official
TNoodle scrambles.
"""

from __future__ import annotations

import random
from typing import Final

from rubiks_cfop.cube.cubie import CORNER_COUNT, EDGE_COUNT, CubieCube
from rubiks_cfop.cube.moves import get_move
from rubiks_cfop.errors import SearchLimitError, SolveTimeoutError
from rubiks_cfop.scramble.scramble import Scramble, ScrambleStyle
from rubiks_cfop.solver.tables import PHASE1_MOVE_NAMES
from rubiks_cfop.solver.two_phase import SearchLimits, solve

__all__ = [
    "DEFAULT_MAX_LENGTH",
    "MIN_SOLVABLE_MOVES",
    "random_state",
    "random_state_scramble",
    "random_state_scrambles",
]

#: WCA 4b3: the state must need at least this many moves to solve.
MIN_SOLVABLE_MOVES: Final = 2

#: Target upper bound for a generated scramble, in moves.
DEFAULT_MAX_LENGTH: Final = 22

#: Targets below this are not attempted.  A two-phase search for a shorter
#: scramble costs far more than it is worth: measured over six states, a target of
#: 22 takes about 0.2 s, 21 about 0.1 s, 20 about 4 s, and anything below that runs
#: away.  WCA scrambles sit around 20 to 22 moves anyway.
MIN_TARGET_LENGTH: Final = 21

#: How many times to redraw a state if the search cannot handle it.
_MAX_ATTEMPTS: Final = 8

#: Search budget for one attempt, in nodes.  A two-phase search usually finishes in
#: a fraction of a second, but a few states take much longer; giving up on those and
#: drawing a fresh state keeps scramble generation responsive, which is allowed
#: because WCA 4b3 constrains the distribution of states, not which state is drawn.
#: The budget is counted in nodes rather than milliseconds so that a seed gives the
#: same scramble on every machine, however loaded: 400,000 nodes is about a second.
_ATTEMPT_MAX_NODES: Final = 400_000


def _random_permutation(rng: random.Random, size: int) -> list[int]:
    """Return a uniformly random permutation of ``0..size-1``."""
    values = list(range(size))
    rng.shuffle(values)
    return values


def _random_orientations(rng: random.Random, size: int, modulus: int) -> list[int]:
    """Return orientations whose sum is a multiple of ``modulus``.

    The last orientation is derived from the others, which is what makes the
    resulting state reachable.
    """
    orientations = [rng.randrange(modulus) for _ in range(size - 1)]
    orientations.append(-sum(orientations) % modulus)
    return orientations


def _permutation_parity(permutation: list[int]) -> int:
    """Return 0 for an even permutation and 1 for an odd one."""
    inversions = 0
    for index, value in enumerate(permutation):
        inversions += sum(1 for other in permutation[index + 1 :] if other < value)
    return inversions % 2


def random_state(rng: random.Random) -> CubieCube:
    """Return a uniformly random solvable cube state.

    Corner and edge permutations are drawn independently and then repaired: when
    their parities disagree, two edges are swapped, which is a bijection between
    the mismatched and the matching pairs, so the result is still uniform.

    Args:
        rng: The random source, so callers can seed it.

    Returns:
        A solvable random state.
    """
    cp = _random_permutation(rng, CORNER_COUNT)
    ep = _random_permutation(rng, EDGE_COUNT)
    if _permutation_parity(cp) != _permutation_parity(ep):
        ep[0], ep[1] = ep[1], ep[0]
    return CubieCube(
        cp=tuple(cp),
        co=tuple(_random_orientations(rng, CORNER_COUNT, 3)),
        ep=tuple(ep),
        eo=tuple(_random_orientations(rng, EDGE_COUNT, 2)),
    )


def _needs_at_least_two_moves(state: CubieCube) -> bool:
    """Return whether a state is legal under WCA 4b3, needing two or more moves."""
    if state.is_solved():
        return False
    return not any(state.apply(name).is_solved() for name in PHASE1_MOVE_NAMES)


def random_state_scramble(
    *,
    seed: int | None = None,
    length: int | None = None,
    limits: SearchLimits | None = None,
) -> Scramble:
    """Generate a random-state scramble.

    Args:
        seed: Seed for reproducible output; a fresh seed is drawn when omitted.
        length: Target upper bound for the scramble, in moves.  Defaults to
            :data:`DEFAULT_MAX_LENGTH`.  When a state cannot be solved inside the
            target, the search is relaxed to the default bound rather than failing:
            WCA 4b3 constrains the state, not the length.
        limits: Explicit search limits, overriding ``length``.

    Returns:
        The scramble and the random state it produces.

    Raises:
        ValueError: If ``length`` is not positive.
        SearchLimitError: If the search failed for every state it tried.
    """
    if length is not None and length < 1:
        raise ValueError(f"length must be positive, got {length}")
    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)  # noqa: S311 - reproducible by design

    target = DEFAULT_MAX_LENGTH if length is None else length
    if target < MIN_TARGET_LENGTH:
        # Searching for a scramble this short is far more expensive than it is
        # useful, and WCA 4b3 constrains the state rather than the length.
        target = DEFAULT_MAX_LENGTH
    if limits is None:
        first_limits: SearchLimits | None = SearchLimits(
            max_total_depth=target, max_nodes=_ATTEMPT_MAX_NODES
        )
        second_limits: SearchLimits | None = (
            SearchLimits(max_total_depth=DEFAULT_MAX_LENGTH, max_nodes=_ATTEMPT_MAX_NODES)
            if target < DEFAULT_MAX_LENGTH
            else None
        )
    else:
        first_limits, second_limits = limits, None

    for _ in range(_MAX_ATTEMPTS):
        state = random_state(rng)
        if not _needs_at_least_two_moves(state):
            continue
        solution = _attempt(state, first_limits, second_limits)
        if solution is None:
            continue
        # The scramble is the sequence that *builds* the state, so it is the
        # inverse of the solution.
        moves = tuple(get_move(name).inverse() for name in reversed(solution))
        return Scramble.from_moves(moves, style=ScrambleStyle.RANDOM_STATE, seed=seed)

    raise SearchLimitError(  # pragma: no cover - the search is roomy by default
        "could not solve any random state within the limits",
        attempts=_MAX_ATTEMPTS,
    )


def _attempt(
    state: CubieCube,
    first_limits: SearchLimits,
    second_limits: SearchLimits | None,
) -> tuple[str, ...] | None:
    """Try to solve ``state``, relaxing the target if needed.

    Returns ``None`` when this state should be abandoned: the search ran out of
    budget, or it hit its depth limit with no relaxation left.
    """
    try:
        return solve(state, limits=first_limits)
    except SolveTimeoutError:
        return None
    except SearchLimitError:
        if second_limits is None:
            return None
    try:
        return solve(state, limits=second_limits)
    except (SolveTimeoutError, SearchLimitError):
        return None


def random_state_scrambles(
    count: int,
    *,
    seed: int | None = None,
    length: int | None = None,
    limits: SearchLimits | None = None,
) -> list[Scramble]:
    """Generate ``count`` independent random-state scrambles.

    Args:
        count: How many scrambles to produce.
        seed: Seed for the whole sequence; each scramble derives its own seed.
        length: Upper bound for each scramble, in moves.
        limits: Explicit search limits, overriding ``length``.

    Returns:
        The scrambles, in order.

    Raises:
        ValueError: If ``count`` is negative or ``length`` is not positive.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)  # noqa: S311 - reproducible by design
    return [
        random_state_scramble(seed=rng.randrange(2**32), length=length, limits=limits)
        for _ in range(count)
    ]

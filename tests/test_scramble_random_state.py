"""Random-state scrambles (WCA Regulation 4b3)."""

from __future__ import annotations

import random

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.cubie import CubieCube
from rubiks_cfop.cube.moves import MOVES
from rubiks_cfop.errors import SearchLimitError, SolveTimeoutError
from rubiks_cfop.scramble import (
    Scramble,
    ScrambleStyle,
    generate_scramble,
    generate_scrambles,
    random_state_scramble,
    random_state_scrambles,
)
from rubiks_cfop.scramble import random_state as random_state_module
from rubiks_cfop.scramble.random_state import (
    DEFAULT_MAX_LENGTH,
    MIN_SOLVABLE_MOVES,
    MIN_TARGET_LENGTH,
    _needs_at_least_two_moves,
    random_state,
)
from rubiks_cfop.solver.two_phase import SearchLimits, solve

FACE_MOVES = [name for name in MOVES if MOVES[name].kind == "face"]


@pytest.fixture(scope="module")
def scrambles() -> list[Scramble]:
    """A handful of scrambles, generated once: solving is the expensive part."""
    return [random_state_scramble(seed=seed) for seed in range(4)]


def test_random_state_is_solvable_and_canonical() -> None:
    rng = random.Random(11)
    for _ in range(50):
        state = random_state(rng)
        assert state.is_solvable()
        cubie = Cube.from_facelets(state.to_facelets()).cubie()
        assert cubie == state


def test_random_states_are_not_all_the_same() -> None:
    rng = random.Random(12)
    states = {random_state(rng).to_facelets() for _ in range(50)}
    assert len(states) == 50


def test_random_state_distribution_smoke_test() -> None:
    """Corner twists, edge flips and slice positions should all appear."""
    rng = random.Random(13)
    twists = [0] * 27
    flips = [0] * 16
    for _ in range(600):
        state = random_state(rng)
        twists[sum(o * 3**i for i, o in enumerate(state.co[:4])) % 27] += 1
        flips[sum(o * 2**i for i, o in enumerate(state.eo[:4])) % 16] += 1
    assert all(count > 0 for count in twists)
    assert all(count > 0 for count in flips)
    # A uniform distribution would give 600/27 per bucket; allow a wide margin.
    assert all(5 <= count <= 90 for count in twists)
    assert all(10 <= count <= 80 for count in flips)


def test_permutation_parities_are_balanced() -> None:
    rng = random.Random(14)
    parities = [0, 0]
    for _ in range(200):
        state = random_state(rng)
        inversions = sum(
            1 for i, value in enumerate(state.cp) for other in state.cp[i + 1 :] if other < value
        )
        parities[inversions % 2] += 1
    assert min(parities) > 60  # roughly balanced


def test_scramble_builds_exactly_the_random_state(scrambles: list[Scramble]) -> None:
    for scramble in scrambles:
        assert Cube.solved().apply_moves(scramble.moves) == scramble.state
        assert scramble.state.is_solvable()
        assert not scramble.state.is_solved()


def test_scramble_solves_its_own_state(scrambles: list[Scramble]) -> None:
    scramble = scrambles[0]
    solution = solve(scramble.state.cubie(), limits=SearchLimits(max_total_depth=24))
    assert scramble.state.cubie().apply_moves(solution).is_solved()


def test_scramble_length_bounds(scrambles: list[Scramble]) -> None:
    for scramble in scrambles:
        assert MIN_SOLVABLE_MOVES <= scramble.length <= DEFAULT_MAX_LENGTH


def test_scramble_respects_a_custom_length() -> None:
    """A generous target is always met."""
    assert random_state_scramble(seed=31, length=DEFAULT_MAX_LENGTH).length <= DEFAULT_MAX_LENGTH


def test_scramble_ignores_an_impossibly_short_target() -> None:
    """A target below the useful floor falls back to the default length."""
    scramble = random_state_scramble(seed=31, length=10)
    assert MIN_SOLVABLE_MOVES <= scramble.length <= DEFAULT_MAX_LENGTH
    assert Cube.solved().apply_moves(scramble.moves) == scramble.state


def test_scramble_meets_the_lowest_useful_target() -> None:
    scramble = random_state_scramble(seed=17, length=MIN_TARGET_LENGTH)
    assert MIN_SOLVABLE_MOVES <= scramble.length <= MIN_TARGET_LENGTH


def test_tight_target_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the target cannot be met, the search relaxes instead of failing."""
    depths: list[int | None] = []
    real_solve = random_state_module.solve

    def fake_solve(state, *, limits=None, cancel=None):
        depths.append(None if limits is None else limits.max_total_depth)
        if len(depths) == 1:
            raise SearchLimitError("too tight")
        return real_solve(state, limits=limits, cancel=cancel)

    monkeypatch.setattr(random_state_module, "solve", fake_solve)
    scramble = random_state_scramble(seed=1, length=MIN_TARGET_LENGTH)
    assert depths[0] == MIN_TARGET_LENGTH
    assert depths[1] == DEFAULT_MAX_LENGTH
    assert scramble.length <= DEFAULT_MAX_LENGTH


def test_abandoned_states_are_redrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """A state whose search times out must be replaced, not returned."""
    calls = [0]
    real_solve = random_state_module.solve

    def fake_solve(state, *, limits=None, cancel=None):
        calls[0] += 1
        if calls[0] == 1:
            raise SolveTimeoutError("too slow")
        return real_solve(state, limits=limits, cancel=cancel)

    monkeypatch.setattr(random_state_module, "solve", fake_solve)
    scramble = random_state_scramble(seed=1)
    assert calls[0] >= 2
    assert scramble.length >= MIN_SOLVABLE_MOVES


def test_the_relaxed_attempt_can_also_be_abandoned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the target attempt and the relaxed one are allowed to give up."""
    depths: list[int | None] = []
    real_solve = random_state_module.solve

    def fake_solve(state, *, limits=None, cancel=None):
        depths.append(None if limits is None else limits.max_total_depth)
        if len(depths) == 1:
            raise SearchLimitError("too tight")
        if len(depths) == 2:
            raise SolveTimeoutError("too slow")
        return real_solve(state, limits=limits, cancel=cancel)

    monkeypatch.setattr(random_state_module, "solve", fake_solve)
    scramble = random_state_scramble(seed=2, length=MIN_TARGET_LENGTH)
    assert depths[:2] == [MIN_TARGET_LENGTH, DEFAULT_MAX_LENGTH]
    assert scramble.length >= MIN_SOLVABLE_MOVES


@pytest.mark.parametrize("length", [0, -3])
def test_length_must_be_positive(length: int) -> None:
    with pytest.raises(ValueError, match="length must be positive"):
        random_state_scramble(seed=1, length=length)


def test_scramble_is_deterministic(scrambles: list[Scramble]) -> None:
    first = random_state_scramble(seed=1)
    assert first == scrambles[1]
    assert first.to_dict() == scrambles[1].to_dict()


def test_scramble_records_its_seed_and_style(scrambles: list[Scramble]) -> None:
    scramble = scrambles[2]
    assert scramble.seed == 2
    assert scramble.style is ScrambleStyle.RANDOM_STATE
    assert scramble.to_dict()["style"] == "random-state"
    assert Scramble.from_dict(scramble.to_dict()) == scramble


def test_generate_scramble_defaults_to_random_state(scrambles: list[Scramble]) -> None:
    scramble = generate_scramble(seed=0)
    assert scramble.style is ScrambleStyle.RANDOM_STATE
    assert scramble == scrambles[0]


def test_generate_scramble_can_still_use_random_move() -> None:
    scramble = generate_scramble(seed=5, style="random-move")
    assert scramble.style is ScrambleStyle.RANDOM_MOVE
    assert scramble.length == 20


def test_generate_scrambles_batch() -> None:
    batch = generate_scrambles(2, seed=4242)
    assert len(batch) == 2
    assert len({scramble.text for scramble in batch}) == 2
    assert all(scramble.style is ScrambleStyle.RANDOM_STATE for scramble in batch)


def test_generate_scrambles_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        generate_scrambles(-1)


def test_explicit_search_limits_are_used() -> None:
    scramble = random_state_scramble(
        seed=8, limits=SearchLimits(max_total_depth=DEFAULT_MAX_LENGTH)
    )
    assert scramble.length <= DEFAULT_MAX_LENGTH


def test_batch_without_a_seed() -> None:
    batch = random_state_scrambles(2)
    assert len({scramble.seed for scramble in batch}) == 2
    assert all(scramble.state.is_solvable() for scramble in batch)


def test_batch_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        random_state_scrambles(-1)


def test_scramble_without_a_seed_still_works() -> None:
    scramble = random_state_scramble()
    assert isinstance(scramble.seed, int)


def test_states_needing_fewer_than_two_moves_are_rejected() -> None:
    assert not _needs_at_least_two_moves(CubieCube.solved())
    one_move = CubieCube.solved().apply("R")
    assert not _needs_at_least_two_moves(one_move)
    assert _needs_at_least_two_moves(CubieCube.solved().apply_moves(["R", "U"]))


def test_trivial_states_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A state that needs fewer than two moves must be redrawn, not returned."""
    monkeypatch.setattr(random_state_module, "random_state", lambda rng: CubieCube.solved())
    with pytest.raises(SearchLimitError, match="could not solve any random state"):
        random_state_scramble(seed=1)


def test_explicit_limits_that_are_too_tight_fail_loudly() -> None:
    with pytest.raises(SearchLimitError):
        random_state_scramble(seed=1, limits=SearchLimits(max_total_depth=4))

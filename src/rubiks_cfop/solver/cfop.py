"""The CFOP pipeline: cross, four F2L pairs, OLL, PLL.

This is the module the CLI and any GUI talk to.  It runs the four stages in order,
collects one :class:`Stage` per step, and verifies that the concatenated solution
really solves the cube before returning it -- a solution that does not check out is
a bug, not a result.

The cross is always solved into the bottom layer, and the cube is reoriented first
so that the chosen color is at the bottom: for a white cross the top face is
yellow, which is the orientation every stage after the cross assumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.moves import Move, MoveKind, get_move
from rubiks_cfop.cube.notation import format_moves
from rubiks_cfop.errors import RubiksError, UnsolvableStateError
from rubiks_cfop.solver.cross import (
    COLOR_ORDER,
    CrossResult,
    solve_best_cross,
    solve_cross_for_color,
)
from rubiks_cfop.solver.f2l import F2LResult, display_cubie, solve_f2l
from rubiks_cfop.solver.last_layer import (
    oll_pattern,
    solve_oll,
    solve_pll,
)
from rubiks_cfop.solver.two_phase import solve

if TYPE_CHECKING:
    from collections.abc import Callable

    from rubiks_cfop.cube.cube import Cube
    from rubiks_cfop.cube.facelets import Color

__all__ = [
    "CrossOption",
    "Solution",
    "Stage",
    "cross_options",
    "solve_cube",
]

#: Turns of the top face, used to align the last layer before finishing.
AUF_NAMES: Final[tuple[str, ...]] = ("U", "U2", "U'")


@dataclass(frozen=True, slots=True)
class CrossOption:
    """One of the six possible crosses, with what it would cost."""

    color: Color
    length: int
    moves: tuple[Move, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view."""
        return {
            "color": self.color.value,
            "length": self.length,
            "moves": [move.name for move in self.moves],
        }


@dataclass(frozen=True, slots=True)
class Stage:
    """One step of a solution.

    Attributes:
        label: How the stage is reported, e.g. ``"F2L2"`` or ``"OLL (27)"``.
        kind: ``cross``, ``f2l``, ``oll`` or ``pll``.
        moves: The moves of the stage.
        after: The cube after the stage.
        metadata: Extra facts, such as the pair slot or the OLL number.
    """

    label: str
    kind: str
    moves: tuple[Move, ...]
    after: Cube
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return the stage's moves in canonical notation."""
        return format_moves(self.moves)

    @property
    def length(self) -> int:
        """Return the number of moves in the stage."""
        return len(self.moves)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the stage."""
        return {
            "label": self.label,
            "kind": self.kind,
            "moves": [move.name for move in self.moves],
            "text": self.text,
            "length": self.length,
            "facelets": self.after.facelets,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class Solution:
    """A complete CFOP solution.

    Attributes:
        initial: The cube as it was handed in.
        scramble: The scramble that produced it, when there was one.
        cross_color: The color of the cross.
        rotation: The rotation applied so the cross sits at the bottom.
        stages: The stages, in order.
        final: The cube after the last stage; it must be solved.
    """

    initial: Cube
    cross_color: Color
    rotation: tuple[Move, ...]
    stages: tuple[Stage, ...]
    final: Cube
    scramble: str | None = None

    @property
    def moves(self) -> tuple[Move, ...]:
        """Return every move of the solution, in order."""
        return tuple(move for stage in self.stages for move in stage.moves)

    @property
    def total_moves(self) -> int:
        """Return the number of moves in the solution."""
        return sum(stage.length for stage in self.stages)

    @property
    def verified(self) -> bool:
        """Return whether the solution really solves the cube."""
        return self.final.is_solved()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the whole solution."""
        return {
            "scramble": self.scramble,
            "cross_color": self.cross_color.value,
            "rotation": format_moves(self.rotation),
            "stages": [stage.to_dict() for stage in self.stages],
            "total_moves": self.total_moves,
            "verified": self.verified,
            "final_facelets": self.final.facelets,
        }


def cross_options(cube: Cube) -> tuple[CrossOption, ...]:
    """Return the six possible crosses, shortest first.

    Ties keep the documented color order, so the list is stable.
    """
    options: list[CrossOption] = []
    for color in COLOR_ORDER:
        result = solve_cross_for_color(cube, color)
        options.append(CrossOption(color=color, length=result.length, moves=result.moves))
    return tuple(
        sorted(options, key=lambda option: (option.length, COLOR_ORDER.index(option.color)))
    )


def _simplify(moves: tuple[Move, ...]) -> tuple[Move, ...]:
    """Merge adjacent turns of the same face, leaving other moves alone."""
    result: list[Move] = []
    for move in moves:
        if result and result[-1].base == move.base and move.kind is MoveKind.FACE:
            previous = result.pop()
            turns = (previous.turns + move.turns) % 4
            if turns:
                suffix = {1: "", 2: "2", 3: "'"}[turns]
                result.append(get_move(f"{move.base}{suffix}"))
        else:
            result.append(move)
    return tuple(result)


def _cross(cube: Cube, cross: Color | str) -> CrossResult:
    """Solve the cross that was asked for, or the best one."""
    if isinstance(cross, str) and cross == "best":
        return solve_best_cross(cube)
    return solve_cross_for_color(cube, cross)


def _auf_to_solve(cube: Cube) -> tuple[Move, ...]:
    """Return the turn of the top face that solves ``cube``, if any."""
    if cube.is_solved():
        return ()
    for name in AUF_NAMES:
        move = get_move(name)
        if cube.apply(move).is_solved():
            return (move,)
    return ()


def solve_cube(
    cube: Cube,
    *,
    cross: Color | str = "best",
    scramble: str | None = None,
) -> Solution:
    """Solve a cube with CFOP.

    Args:
        cube: The scrambled cube.
        cross: The cross color, or ``"best"`` for the shortest of the six.
        scramble: The scramble that produced ``cube``, recorded in the result.

    Returns:
        The solved stages, with the cube after each one.

    Raises:
        UnsolvableStateError: If the cube is not solvable.
        SearchLimitError: If a stage cannot be solved.
        RubiksError: If the assembled solution does not solve the cube, which would
            be a bug in one of the stages.
    """
    started = _cross(cube, cross)
    stages: list[Stage] = [
        Stage(
            label="Cross",
            kind="cross",
            moves=(*started.rotation, *started.moves),
            after=started.after,
            metadata={"color": started.color.value, "rotation": format_moves(started.rotation)},
        )
    ]
    current = started.after

    for index, pair in enumerate(solve_f2l(current), start=1):
        stages.append(_f2l_stage(index, pair))
        current = pair.after

    stages.append(_safe_stage(_oll_stage, current, "oll", "OLL (skip)"))
    current = stages[-1].after
    stages.append(_safe_stage(_pll_stage, current, "pll", "PLL (skip)"))
    current = stages[-1].after
    if not current.is_solved():
        # Every stage has a fallback, and so has the pipeline: whatever is left is
        # finished with the two-phase solver, so a solution is always complete.  The
        # moves are applied to the display, so the state must be projected in the
        # display frame: ``Cube.cubie`` would undo the cross rotation first and the
        # rescue would then turn the wrong faces.
        rescue = solve(display_cubie(current))
        finished = current.apply_moves(rescue)
        stages.append(
            Stage(
                label="Finish (two-phase)",
                kind="rescue",
                moves=tuple(get_move(name) for name in rescue),
                after=finished,
                metadata={"reason": "a last-layer table entry did not finish the cube"},
            )
        )
        current = finished

    solution = Solution(
        initial=cube,
        cross_color=started.color,
        rotation=started.rotation,
        stages=tuple(stages),
        final=current,
        scramble=scramble,
    )
    if not solution.verified:
        raise RubiksError(
            "the assembled solution does not solve the cube",
            stages=[stage.label for stage in stages],
        )
    return solution


def _f2l_stage(index: int, pair: F2LResult) -> Stage:
    """Build the stage for one inserted pair."""
    return Stage(
        label=f"F2L{index}",
        kind="f2l",
        moves=_simplify(pair.moves),
        after=pair.after,
        metadata={
            "slot": pair.slot,
            "case": None if pair.case is None else pair.case.label,
            "case_name": None if pair.case is None else pair.case.name,
        },
    )


def _safe_stage(
    build: Callable[[Cube], Stage],
    current: Cube,
    kind: str,
    label: str,
) -> Stage:
    """Build a last-layer stage, falling back to a skip if the table has no case.

    A last-layer state that the table cannot name is not a failure: the pipeline's
    two-phase rescue finishes the cube and the stage is reported as skipped.
    """
    try:
        return build(current)
    except UnsolvableStateError:
        return Stage(
            label=label,
            kind=kind,
            moves=(),
            after=current,
            metadata={"name": "not recognized", "fallback": True},
        )


def _oll_stage(current: Cube) -> Stage:
    """Orient the last layer, or record that it is already oriented."""
    if oll_pattern(display_cubie(current)) == (0, 0, 0, 0, 0, 0, 0, 0):
        return Stage(
            label="OLL (skip)",
            kind="oll",
            moves=(),
            after=current,
            metadata={"number": None, "name": "already oriented"},
        )
    oll = solve_oll(current)
    return Stage(
        label=f"OLL ({oll.label})",
        kind="oll",
        moves=_simplify(oll.moves),
        after=oll.after,
        metadata={"number": int(oll.label), "name": oll.case.name},
    )


def _pll_stage(current: Cube) -> Stage:
    """Permute the last layer, or record that it is already permuted."""
    finish = _auf_to_solve(current)
    if current.is_solved() or finish:
        return Stage(
            label="PLL (skip)",
            kind="pll",
            moves=_simplify(finish),
            after=current.apply_moves(finish),
            metadata={"name": "already permuted", "case": None},
        )
    pll = solve_pll(current)
    final = pll.after
    finish = _auf_to_solve(final)
    return Stage(
        label=f"PLL ({pll.label})",
        kind="pll",
        moves=_simplify((*pll.moves, *finish)),
        after=final.apply_moves(finish),
        metadata={"name": pll.case.name, "case": pll.label},
    )

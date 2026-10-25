"""The interface's state and transitions, with no toolkit in sight.

Everything that is easy to get wrong in a graphical interface lives here, where it
can be tested with plain pytest: turning a :class:`~rubiks_cfop.solver.cfop.Solution`
into a move-by-move timeline, stepping and seeking through it, selecting a stage,
and keeping track of the busy flag and the last error.

The widgets in :mod:`rubiks_cfop.gui.app` only read this state and call its
transitions; they hold no logic of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.notation import parse_scramble

if TYPE_CHECKING:
    from rubiks_cfop.cube.moves import Move
    from rubiks_cfop.errors import NotationError
    from rubiks_cfop.solver.cfop import CrossOption, Solution

__all__ = ["Step", "Timeline", "ViewModel", "parse_input", "token_span"]

#: Marker for the timeline step before any stage has started.
BEFORE_FIRST_STAGE = -1


@dataclass(frozen=True, slots=True)
class Step:
    """One position of the timeline: the cube after a single move.

    Attributes:
        stage: Index of the stage the move belongs to, or
            :data:`BEFORE_FIRST_STAGE` for the scrambled cube.
        move: The move just applied, or ``None`` for the scrambled cube.
        index_in_stage: How many moves of the stage have been applied, 1-based.
        cube: The cube after the move.
    """

    stage: int
    move: Move | None
    index_in_stage: int
    cube: Cube


@dataclass(frozen=True, slots=True)
class Timeline:
    """A solution unrolled into one step per move.

    Step 0 is the scrambled cube; every later step applies exactly one move, so a
    player can show the cube after any move without owning a cube model.
    """

    steps: tuple[Step, ...]
    stage_ends: tuple[int, ...]

    @classmethod
    def from_solution(cls, solution: Solution) -> Timeline:
        """Unroll ``solution`` into a timeline."""
        steps = [Step(BEFORE_FIRST_STAGE, None, 0, solution.initial)]
        ends: list[int] = []
        cube = solution.initial
        for stage_index, stage in enumerate(solution.stages):
            for offset, move in enumerate(stage.moves, start=1):
                cube = cube.apply(move)
                steps.append(Step(stage_index, move, offset, cube))
            ends.append(len(steps) - 1)
        return cls(steps=tuple(steps), stage_ends=tuple(ends))

    @property
    def last(self) -> int:
        """Return the index of the final step."""
        return len(self.steps) - 1

    def stage_start(self, stage: int) -> int:
        """Return the step just before ``stage``'s first move."""
        return 0 if stage == 0 else self.stage_ends[stage - 1]

    def stage_at(self, position: int) -> int:
        """Return the stage a step belongs to, or :data:`BEFORE_FIRST_STAGE`."""
        return self.steps[position].stage


@dataclass(slots=True)
class ViewModel:
    """The mutable state behind the window.

    Attributes:
        cube: The cube being shown when there is no solution yet.
        solution: The current solution, if any.
        timeline: The solution unrolled move by move.
        position: The selected step of the timeline.
        busy: Whether a background job is running.
        status: A one-line message for the status bar.
        error: The last error message, cleared by the next successful action.
        cross_options: The six crosses of the current cube, best first.
        job: A counter that identifies the latest background job, so that results
            of an abandoned job can be ignored.
    """

    cube: Cube = field(default_factory=Cube.solved)
    solution: Solution | None = None
    timeline: Timeline | None = None
    position: int = 0
    busy: bool = False
    status: str = ""
    error: str | None = None
    cross_options: tuple[CrossOption, ...] = ()
    job: int = 0

    # -- background jobs ---------------------------------------------------

    def start_job(self, status: str) -> int:
        """Mark a new background job as running and return its identifier."""
        self.job += 1
        self.busy = True
        self.status = status
        self.error = None
        return self.job

    def is_current(self, job: int) -> bool:
        """Return whether ``job`` is the latest job, whose result should be shown."""
        return job == self.job

    def finish_job(self, status: str = "") -> None:
        """Mark the running job as finished."""
        self.busy = False
        self.status = status

    def fail(self, message: str) -> None:
        """Record an error and stop being busy."""
        self.busy = False
        self.error = message
        self.status = message

    # -- cube and solution -------------------------------------------------

    def set_cube(self, cube: Cube) -> None:
        """Show a new cube, dropping any solution for the previous one."""
        self.cube = cube
        self.solution = None
        self.timeline = None
        self.position = 0
        self.cross_options = ()

    def load_solution(
        self,
        solution: Solution,
        cross_options: tuple[CrossOption, ...] = (),
    ) -> None:
        """Show a solution, starting from the scrambled cube."""
        self.cube = solution.initial
        self.solution = solution
        self.timeline = Timeline.from_solution(solution)
        self.position = 0
        self.cross_options = cross_options

    @property
    def current_cube(self) -> Cube:
        """Return the cube at the selected step."""
        if self.timeline is None:
            return self.cube
        return self.timeline.steps[self.position].cube

    @property
    def last_position(self) -> int:
        """Return the last step, 0 when there is no solution."""
        return 0 if self.timeline is None else self.timeline.last

    @property
    def current_stage(self) -> int:
        """Return the stage of the selected step, or :data:`BEFORE_FIRST_STAGE`."""
        if self.timeline is None:
            return BEFORE_FIRST_STAGE
        return self.timeline.stage_at(self.position)

    def describe_position(self) -> str:
        """Return a short description of the selected step, for the player."""
        if self.timeline is None or self.solution is None:
            return "No solution yet"
        step = self.timeline.steps[self.position]
        prefix = f"Move {self.position}/{self.timeline.last}"
        if step.move is None:
            return f"{prefix} - scrambled cube"
        stage = self.solution.stages[step.stage]
        return f"{prefix} - {stage.label}: {step.move.name} ({step.index_in_stage}/{stage.length})"

    # -- navigation --------------------------------------------------------

    def seek(self, position: int) -> None:
        """Select a step, clamped to the timeline."""
        self.position = max(0, min(position, self.last_position))

    def step(self, delta: int) -> bool:
        """Move ``delta`` steps; return whether the position changed."""
        before = self.position
        self.seek(self.position + delta)
        return self.position != before

    def select_stage(self, stage: int) -> None:
        """Jump to the end of a stage."""
        if self.timeline is not None:
            self.seek(self.timeline.stage_ends[stage])

    def at_end(self) -> bool:
        """Return whether the last step is selected."""
        return self.position >= self.last_position


def parse_input(text: str, mode: str) -> tuple[Cube, str | None]:
    """Turn what the user typed into a cube.

    Args:
        text: A scramble in WCA notation, or a 54 letter facelet string.
        mode: ``"scramble"`` or ``"facelets"``.

    Returns:
        The cube, and the scramble text when one was given.

    Raises:
        NotationError: If a scramble token is not valid notation.
        InvalidStateError: If a facelet string is malformed.
        UnsolvableStateError: If a facelet string cannot occur on a real cube.
    """
    if mode == "facelets":
        cube = Cube.from_facelets(text)
        cube.cubie().validate()
        return cube, None
    stripped = " ".join(text.split())
    return Cube.solved().apply_moves(parse_scramble(stripped)), stripped or None


def token_span(text: str, error: NotationError) -> tuple[int, int] | None:
    """Return the character range of the token a notation error points at."""
    position = 0
    for index, token in enumerate(text.split()):
        start = text.index(token, position)
        position = start + len(token)
        if index == error.index:
            return start, position
    return None

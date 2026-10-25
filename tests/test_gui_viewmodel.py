"""The GUI view-model and net painter: everything testable without a screen."""

from __future__ import annotations

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.errors import InvalidStateError, NotationError
from rubiks_cfop.gui.painter import NetGeometry, hex_color, paint_net
from rubiks_cfop.gui.viewmodel import (
    BEFORE_FIRST_STAGE,
    Timeline,
    ViewModel,
    parse_input,
    token_span,
)
from rubiks_cfop.render.net import DEFAULT_PALETTE, NET_COLUMNS, NET_ROWS, net_layout
from rubiks_cfop.solver.cfop import solve_cube

SCRAMBLE = "R U R' U' F2 D"


@pytest.fixture(scope="module")
def solution():
    return solve_cube(Cube.solved().apply_scramble(SCRAMBLE), scramble=SCRAMBLE)


class RecordingPainter:
    def __init__(self) -> None:
        self.rects: list[tuple[float, float, float, float, str]] = []
        self.texts: list[tuple[float, float, str, str]] = []

    def fill_rect(self, x: float, y: float, width: float, height: float, fill: str) -> None:
        self.rects.append((x, y, width, height, fill))

    def draw_text(self, x: float, y: float, text: str, fill: str) -> None:
        self.texts.append((x, y, text, fill))


def test_timeline_has_one_step_per_move(solution) -> None:
    timeline = Timeline.from_solution(solution)
    assert timeline.last == solution.total_moves
    assert timeline.steps[0].cube == solution.initial
    assert timeline.steps[0].stage == BEFORE_FIRST_STAGE
    assert timeline.steps[-1].cube.is_solved()


def test_timeline_stage_ends_match_stage_states(solution) -> None:
    timeline = Timeline.from_solution(solution)
    for index, stage in enumerate(solution.stages):
        assert timeline.steps[timeline.stage_ends[index]].cube == stage.after
    assert timeline.stage_start(0) == 0
    assert timeline.stage_start(1) == timeline.stage_ends[0]


def test_navigation_is_clamped(solution) -> None:
    model = ViewModel()
    assert model.describe_position() == "No solution yet"
    assert model.current_stage == BEFORE_FIRST_STAGE
    model.load_solution(solution)
    assert model.position == 0
    assert "scrambled cube" in model.describe_position()
    assert not model.step(-1)
    assert model.step(1)
    assert model.current_stage == 0
    assert "Cross" in model.describe_position()
    model.seek(10_000)
    assert model.at_end()
    assert model.current_cube.is_solved()
    model.select_stage(0)
    assert model.current_cube == solution.stages[0].after


def test_set_cube_drops_the_solution(solution) -> None:
    model = ViewModel()
    model.load_solution(solution)
    cube = Cube.solved().apply_scramble("R")
    model.set_cube(cube)
    assert model.solution is None
    assert model.timeline is None
    assert model.current_cube == cube
    assert model.last_position == 0
    model.select_stage(0)  # no solution: nothing to select, and no error
    assert model.position == 0


def test_jobs_ignore_stale_results() -> None:
    model = ViewModel()
    first = model.start_job("one")
    second = model.start_job("two")
    assert model.busy
    assert not model.is_current(first)
    assert model.is_current(second)
    model.finish_job("done")
    assert not model.busy
    assert model.status == "done"
    model.fail("broken")
    assert model.error == "broken"
    assert not model.busy


def test_parse_input_scramble_and_facelets() -> None:
    cube, text = parse_input("  R   U ", "scramble")
    assert text == "R U"
    assert cube == Cube.solved().apply_scramble("R U")
    cube, text = parse_input(cube.facelets, "facelets")
    assert text is None
    assert cube == Cube.solved().apply_scramble("R U")
    assert parse_input("", "scramble") == (Cube.solved(), None)


def test_parse_input_errors() -> None:
    with pytest.raises(NotationError):
        parse_input("R Q", "scramble")
    with pytest.raises(InvalidStateError):
        parse_input("UUU", "facelets")


def test_token_span_points_at_the_bad_token() -> None:
    text = "R  U Q F"
    with pytest.raises(NotationError) as caught:
        parse_input(text, "scramble")
    span = token_span(text, caught.value)
    assert span is not None
    assert text[span[0] : span[1]] == "Q"
    assert token_span(text, NotationError("x", token="Z", index=9)) is None


def test_painter_draws_every_sticker_in_the_traditional_net() -> None:
    cube = Cube.solved().apply_scramble(SCRAMBLE)
    painter = RecordingPainter()
    geometry = NetGeometry(cell=10, gap=0, margin=0)
    paint_net(painter, cube, geometry, show_labels=True)
    assert len(painter.rects) == 54
    layout = net_layout(cube)
    for x, y, width, height, fill in painter.rects:
        assert width == height == 10
        color = layout.cell(int(y // 10), int(x // 10))
        assert color is not None
        assert fill == hex_color(DEFAULT_PALETTE[color])
    # The up face sits above the front face, the down face below it.
    assert {int(x // 10) for x, y, *_ in painter.rects if y < 30} == {3, 4, 5}
    assert {int(x // 10) for x, y, *_ in painter.rects if y >= 60} == {3, 4, 5}
    assert [text for *_, text, _ in painter.texts] == ["U", "R", "F", "D", "L", "B"]


def test_geometry_fits_and_has_gaps() -> None:
    geometry = NetGeometry.fit(1000, 400)
    assert geometry.width <= 1000 + 1e-9
    assert geometry.height <= 400 + 1e-9
    assert NetGeometry.fit(1, 1).cell == 8.0
    base = NetGeometry()
    assert base.cell_origin(0, 3)[0] == base.margin + 3 * base.cell + base.gap
    assert base.width > NET_COLUMNS * base.cell
    assert base.height > NET_ROWS * base.cell


def test_hex_color() -> None:
    assert hex_color((255, 0, 16)) == "#ff0010"

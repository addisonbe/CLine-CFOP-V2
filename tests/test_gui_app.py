"""A smoke test of the Tk window, skipped where no display is available."""

from __future__ import annotations

import time

import pytest

tk = pytest.importorskip("tkinter")

from rubiks_cfop.gui import app as gui_app  # noqa: E402


@pytest.fixture
def window():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    window = gui_app.CubeApp(root, scramble="R U R' U'")
    yield window
    root.destroy()


def pump(window, until, timeout: float = 120.0) -> None:
    """Run the Tk event loop until ``until()`` holds."""
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "timed out waiting for the window"
        window.root.update()
        time.sleep(0.01)


def test_solve_and_step_through(window) -> None:
    pump(window, lambda: not window.model.busy)
    window.solve()
    pump(window, lambda: window.model.solution is not None and not window.model.busy)
    model = window.model
    assert len(window.table.get_children()) == len(model.solution.stages)
    assert "verified" in window.summary_var.get()
    window.step(1)
    assert model.position == 1
    window.seek(model.last_position)
    assert model.current_cube.is_solved()
    window.table.selection_set(window.table.get_children()[0])
    window.root.update()
    assert model.position == model.timeline.stage_ends[0]
    window.seek(0)
    window.toggle_play()
    assert window._playing
    pump(window, lambda: model.position >= 2)
    window.toggle_play()
    assert not window._playing
    assert len(window.canvas.find_all()) >= 54


def test_bad_input_is_reported(window) -> None:
    pump(window, lambda: not window.model.busy)
    window.input_var.set("R Q")
    window.solve()
    assert "position 2" in window.status_var.get()
    assert window.entry.selection_get() == "Q"
    window.mode_var.set("facelets")
    window.input_var.set("UUU")
    window.show_input()
    assert "Invalid cube" in window.status_var.get()


def test_random_scramble(window) -> None:
    pump(window, lambda: not window.model.busy)
    window.style_var.set("random-move")
    window.seed_var.set("7")
    window.randomize()
    pump(window, lambda: not window.model.busy)
    assert window.seed_var.get() == "7"
    assert window.input_var.get()
    window.seed_var.set("seven")
    window.randomize()
    assert "whole number" in window.status_var.get()


def test_parser_defaults() -> None:
    args = gui_app.build_parser().parse_args([])
    assert args.scramble == ""
    assert args.cross == "best"

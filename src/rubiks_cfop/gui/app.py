"""The desktop window, built with Tkinter from the standard library.

The window is a thin view over :class:`~rubiks_cfop.gui.viewmodel.ViewModel`:

* a scramble bar (scramble or facelet input, random scrambles with a seed, the
  scramble style, the cross color and a *Solve* button),
* the unfolded net, drawn through :func:`~rubiks_cfop.gui.painter.paint_net`,
* a player that steps through the solution one move at a time,
* the solution table, one row per stage, which jumps to the end of a stage,
* a status bar.

Anything slow -- building the solver tables, generating a random-state scramble,
solving -- runs on a worker thread.  Workers never touch a widget: they post their
result to a queue that the Tk event loop drains.
"""

from __future__ import annotations

import argparse
import ctypes
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.facelets import Color
from rubiks_cfop.cube.notation import format_moves
from rubiks_cfop.errors import NotationError, RubiksError
from rubiks_cfop.gui.painter import STICKER_OUTLINE, NetGeometry, paint_net
from rubiks_cfop.gui.viewmodel import ViewModel, parse_input, token_span
from rubiks_cfop.scramble import generate_scramble
from rubiks_cfop.solver.cfop import cross_options, solve_cube
from rubiks_cfop.solver.tables import preload

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from rubiks_cfop.cube.cube import Cube
    from rubiks_cfop.scramble import Scramble
    from rubiks_cfop.solver.cfop import CrossOption, Solution

__all__ = ["CubeApp", "main"]

#: How often the event loop drains the worker queue, in milliseconds.
POLL_MS: Final = 40

#: Player speeds, in milliseconds per move.
DEFAULT_SPEED_MS: Final = 400
MIN_SPEED_MS: Final = 60
MAX_SPEED_MS: Final = 1500

CROSS_CHOICES: Final[tuple[str, ...]] = ("best", *[color.value for color in Color])
STYLE_CHOICES: Final[tuple[str, ...]] = ("random-state", "random-move")
INPUT_MODES: Final[tuple[str, ...]] = ("scramble", "facelets")


class TkPainter:
    """A :class:`~rubiks_cfop.gui.painter.Painter` that draws on a Tk canvas."""

    def __init__(self, canvas: tk.Canvas) -> None:
        """Wrap ``canvas``."""
        self._canvas = canvas

    def fill_rect(self, x: float, y: float, width: float, height: float, fill: str) -> None:
        """Draw one sticker."""
        self._canvas.create_rectangle(
            x, y, x + width, y + height, fill=fill, outline=STICKER_OUTLINE, width=2
        )

    def draw_text(self, x: float, y: float, text: str, fill: str) -> None:
        """Draw a face label."""
        self._canvas.create_text(x, y, text=text, fill=fill, font=("Segoe UI", 11, "bold"))


class CubeApp:
    """The main window."""

    def __init__(self, root: tk.Tk, *, scramble: str = "", cross: str = "best") -> None:
        """Build the widgets and start preloading the solver tables."""
        self.root = root
        self.model = ViewModel()
        self._results: queue.Queue[Callable[[], None]] = queue.Queue()
        self._playing = False
        self._play_after: str | None = None

        root.title("rubiks-cfop")
        root.minsize(900, 560)

        self.input_var = tk.StringVar(value=scramble)
        self.mode_var = tk.StringVar(value="scramble")
        self.style_var = tk.StringVar(value="random-state")
        self.seed_var = tk.StringVar()
        self.cross_var = tk.StringVar(value=cross)
        self.labels_var = tk.BooleanVar(value=True)
        self.speed_var = tk.IntVar(value=DEFAULT_SPEED_MS)
        self.position_var = tk.StringVar(value="No solution yet")
        self.status_var = tk.StringVar()
        self.summary_var = tk.StringVar()

        self._build_scramble_bar()
        self._build_body()
        self._build_status_bar()
        self._bind_keys()

        root.after(POLL_MS, self._drain)
        self._run_in_background("Building solver tables...", preload, self._preloaded)
        if scramble:
            self.show_input()
        self.refresh()

    # -- layout ------------------------------------------------------------

    def _build_scramble_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Combobox(
            bar, textvariable=self.mode_var, values=INPUT_MODES, width=9, state="readonly"
        ).pack(side=tk.LEFT)
        self.entry = ttk.Entry(bar, textvariable=self.input_var, font=("Consolas", 11))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        self.entry.bind("<Return>", lambda _event: self.solve())
        self.show_button = ttk.Button(bar, text="Show", command=self.show_input)
        self.show_button.pack(side=tk.LEFT)
        self.solve_button = ttk.Button(bar, text="Solve", command=self.solve)
        self.solve_button.pack(side=tk.LEFT, padx=(4, 0))

        options = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        options.pack(side=tk.TOP, fill=tk.X)
        self.random_button = ttk.Button(options, text="Random scramble", command=self.randomize)
        self.random_button.pack(side=tk.LEFT)
        ttk.Combobox(
            options, textvariable=self.style_var, values=STYLE_CHOICES, width=13, state="readonly"
        ).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(options, text="Seed").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Entry(options, textvariable=self.seed_var, width=12).pack(side=tk.LEFT)
        ttk.Label(options, text="Cross").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Combobox(
            options, textvariable=self.cross_var, values=CROSS_CHOICES, width=8, state="readonly"
        ).pack(side=tk.LEFT)
        ttk.Checkbutton(
            options, text="Face labels", variable=self.labels_var, command=self.refresh
        ).pack(side=tk.LEFT, padx=(12, 0))

    def _build_body(self) -> None:
        body = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(body)
        geometry = NetGeometry()
        self.canvas = tk.Canvas(
            left,
            width=geometry.width,
            height=geometry.height,
            background="#2b2b2b",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self._build_player(left)
        body.add(left, weight=3)

        right = ttk.Frame(body)
        columns = ("stage", "moves", "count")
        self.table = ttk.Treeview(right, columns=columns, show="headings", selectmode="browse")
        for column, title, width, stretch in (
            ("stage", "Stage", 130, False),
            ("moves", "Moves", 280, True),
            ("count", "#", 40, False),
        ):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, stretch=stretch, anchor=tk.W)
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<<TreeviewSelect>>", self._stage_selected)
        ttk.Label(right, textvariable=self.summary_var, wraplength=420, justify=tk.LEFT).pack(
            side=tk.BOTTOM, fill=tk.X, pady=(6, 0)
        )
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body.add(right, weight=2)

    def _build_player(self, parent: ttk.Frame) -> None:
        player = ttk.Frame(parent, padding=(0, 6, 0, 0))
        player.pack(side=tk.TOP, fill=tk.X)
        self.player_buttons: list[ttk.Button] = []
        for text, command in (
            ("|<", lambda: self.seek(0)),
            ("<", lambda: self.step(-1)),
            ("Play", self.toggle_play),
            (">", lambda: self.step(1)),
            (">|", lambda: self.seek(self.model.last_position)),
        ):
            button = ttk.Button(player, text=text, width=5, command=command)
            button.pack(side=tk.LEFT, padx=1)
            self.player_buttons.append(button)
        self.play_button = self.player_buttons[2]
        ttk.Label(player, text="Speed").pack(side=tk.LEFT, padx=(12, 2))
        ttk.Scale(
            player,
            from_=MAX_SPEED_MS,
            to=MIN_SPEED_MS,
            variable=self.speed_var,
            orient=tk.HORIZONTAL,
            length=120,
        ).pack(side=tk.LEFT)
        ttk.Label(parent, textvariable=self.position_var, font=("Consolas", 10)).pack(
            side=tk.TOP, anchor=tk.W, pady=(4, 0)
        )

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 2, 8, 6))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.progress.pack(side=tk.RIGHT)
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _bind_keys(self) -> None:
        self.root.bind("<Left>", lambda event: self._unless_typing(event, lambda: self.step(-1)))
        self.root.bind("<Right>", lambda event: self._unless_typing(event, lambda: self.step(1)))
        self.root.bind("<space>", lambda event: self._unless_typing(event, self.toggle_play))
        self.root.bind("<Home>", lambda event: self._unless_typing(event, lambda: self.seek(0)))
        self.root.bind(
            "<End>",
            lambda event: self._unless_typing(event, lambda: self.seek(self.model.last_position)),
        )

    def _unless_typing(self, event: tk.Event, action: Callable[[], None]) -> str | None:
        """Run a keyboard shortcut, except while the user is typing in an entry."""
        if isinstance(event.widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        action()
        return "break"

    # -- drawing -----------------------------------------------------------

    def draw(self) -> None:
        """Redraw the net for the selected step."""
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        geometry = NetGeometry.fit(width, height) if width > 1 and height > 1 else NetGeometry()
        paint_net(
            TkPainter(self.canvas),
            self.model.current_cube,
            geometry,
            show_labels=self.labels_var.get(),
        )

    def refresh(self) -> None:
        """Bring every widget in line with the view-model."""
        self.draw()
        self.position_var.set(self.model.describe_position())
        self.status_var.set(self.model.status)
        busy = self.model.busy
        for button in (self.solve_button, self.random_button, self.show_button):
            button.state(["disabled"] if busy else ["!disabled"])
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        stage = self.model.current_stage
        rows = self.table.get_children()
        if 0 <= stage < len(rows):
            if self.table.selection() != (rows[stage],):
                self.table.selection_set(rows[stage])
            self.table.see(rows[stage])
        elif self.table.selection():
            self.table.selection_remove(*self.table.selection())

    def _fill_table(self) -> None:
        self.table.delete(*self.table.get_children())
        solution = self.model.solution
        if solution is None:
            self.summary_var.set("")
            return
        for stage in solution.stages:
            self.table.insert("", tk.END, values=(stage.label, stage.text or "-", stage.length))
        rotation = format_moves(solution.rotation) or "none"
        crosses = ", ".join(
            f"{option.color.value} {option.length}" for option in self.model.cross_options
        )
        verified = "verified" if solution.verified else "NOT verified"
        self.summary_var.set(
            f"Cross color: {solution.cross_color.value} (bottom layer)   "
            f"Orientation: {rotation}\n"
            f"Total: {solution.total_moves} moves, {verified}\n"
            f"Cross lengths: {crosses}"
        )

    # -- actions -----------------------------------------------------------

    def _read_input(self) -> tuple[Cube, str | None] | None:
        """Parse the entry, reporting problems in the status bar."""
        text = self.input_var.get()
        try:
            return parse_input(text, self.mode_var.get())
        except NotationError as error:
            span = token_span(text, error)
            if span is not None:
                self.entry.focus_set()
                self.entry.selection_range(*span)
                self.entry.icursor(span[1])
            self.model.fail(f"Invalid move {error.token!r} at position {error.index + 1}")
        except RubiksError as error:
            self.model.fail(f"Invalid cube: {error}")
        self.refresh()
        return None

    def show_input(self) -> None:
        """Show the typed cube without solving it."""
        self.stop()
        parsed = self._read_input()
        if parsed is None:
            return
        self.model.set_cube(parsed[0])
        self.model.error = None
        self.model.status = "Showing the scrambled cube"
        self._fill_table()
        self.refresh()

    def solve(self) -> None:
        """Solve the typed cube on a worker thread."""
        if self.model.busy:
            return
        self.stop()
        parsed = self._read_input()
        if parsed is None:
            return
        cube, scramble = parsed
        cross = self.cross_var.get()
        self.model.set_cube(cube)
        self._fill_table()

        def work() -> tuple[Solution, tuple[CrossOption, ...]]:
            return solve_cube(cube, cross=cross, scramble=scramble), cross_options(cube)

        def done(result: tuple[Solution, tuple[CrossOption, ...]]) -> None:
            solution, options = result
            self.model.load_solution(solution, options)
            self._fill_table()
            self.model.finish_job(f"Solved in {solution.total_moves} moves")

        self._run_in_background("Solving...", work, done)

    def randomize(self) -> None:
        """Generate a scramble on a worker thread and show it."""
        if self.model.busy:
            return
        self.stop()
        seed_text = self.seed_var.get().strip()
        try:
            seed = int(seed_text) if seed_text else None
        except ValueError:
            self.model.fail(f"The seed must be a whole number, not {seed_text!r}")
            self.refresh()
            return
        style = self.style_var.get()

        def work() -> Scramble:
            return generate_scramble(style=style, seed=seed)

        def done(scramble: Scramble) -> None:
            self.mode_var.set("scramble")
            self.input_var.set(scramble.text)
            self.seed_var.set(str(scramble.seed))
            self.model.set_cube(scramble.state)
            self._fill_table()
            self.model.finish_job(f"Scramble generated (seed {scramble.seed})")

        self._run_in_background("Generating a scramble...", work, done)

    def seek(self, position: int) -> None:
        """Jump to a step of the solution."""
        self.stop()
        self.model.seek(position)
        self.refresh()

    def step(self, delta: int) -> None:
        """Step forwards or backwards through the solution."""
        self.stop()
        self.model.step(delta)
        self.refresh()

    def toggle_play(self) -> None:
        """Start or pause the move-by-move animation."""
        if self._playing:
            self.stop()
            return
        if self.model.timeline is None:
            return
        if self.model.at_end():
            self.model.seek(0)
        self._playing = True
        self.play_button.configure(text="Pause")
        self._tick()

    def stop(self) -> None:
        """Pause the animation."""
        self._playing = False
        self.play_button.configure(text="Play")
        if self._play_after is not None:
            self.root.after_cancel(self._play_after)
            self._play_after = None

    def _tick(self) -> None:
        self._play_after = None
        if not self._playing:
            return
        self.refresh()
        if not self.model.step(1):
            self.stop()
            return
        self._play_after = self.root.after(self.speed_var.get(), self._tick)

    def _stage_selected(self, _event: tk.Event) -> None:
        selection = self.table.selection()
        if not selection or self.model.timeline is None:
            return
        stage = self.table.index(selection[0])
        if stage != self.model.current_stage:
            self.stop()
            self.model.select_stage(stage)
            self.refresh()

    # -- threading ---------------------------------------------------------

    def _run_in_background[T](
        self,
        status: str,
        work: Callable[[], T],
        done: Callable[[T], None],
    ) -> None:
        """Run ``work`` on a worker thread and hand its result to ``done``.

        ``done`` runs on the Tk thread, and only if no newer job has started.
        """
        job = self.model.start_job(status)
        self.refresh()

        def target() -> None:
            try:
                result = work()
            except RubiksError as error:
                message = str(error)
                self._results.put(lambda: self._failed(job, message))
                return
            self._results.put(lambda: self._finished(job, done, result))

        threading.Thread(target=target, daemon=True).start()

    def _finished[T](self, job: int, done: Callable[[T], None], result: T) -> None:
        if not self.model.is_current(job):
            return
        done(result)
        if self.model.busy:
            self.model.finish_job(self.model.status)
        self.refresh()

    def _failed(self, job: int, message: str) -> None:
        if self.model.is_current(job):
            self.model.fail(message)
            self.refresh()

    def _preloaded(self, _result: None) -> None:
        self.model.finish_job("Ready")

    def _drain(self) -> None:
        """Run the callbacks posted by worker threads, then reschedule."""
        while True:
            try:
                callback = self._results.get_nowait()
            except queue.Empty:
                break
            callback()
        self.root.after(POLL_MS, self._drain)


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for ``rubiks-cfop-gui``."""
    parser = argparse.ArgumentParser(
        prog="rubiks-cfop-gui",
        description="A desktop window to scramble and solve the cube with CFOP.",
    )
    parser.add_argument("--scramble", default="", help="a scramble to show at start-up")
    parser.add_argument(
        "--cross", choices=CROSS_CHOICES, default="best", help="the cross color to preselect"
    )
    return parser


def _enable_high_dpi() -> None:
    """Ask Windows for crisp rendering on high-DPI screens, instead of bitmap scaling."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):  # pragma: no cover - older Windows versions
        return


def main(argv: Sequence[str] | None = None) -> int:
    """Open the window and run the Tk event loop."""
    args = build_parser().parse_args(argv)
    _enable_high_dpi()
    root = tk.Tk()
    CubeApp(root, scramble=args.scramble, cross=args.cross)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())

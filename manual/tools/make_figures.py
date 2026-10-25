"""Generate the LaTeX net figures used by the manual, straight from the engine.

The figures are derived from the same renderer the CLI uses, so the manual can
never drift from the program.  Run it with ``uv run python manual/tools/make_figures.py``.

Every cell becomes a ``\\cubecell{<color>}`` (a colored square) or ``\\cubeblank``,
laid out as nine rows of twelve cells: the front face in the middle, U above it,
D below it, and L, F, R, B across the middle band.
"""

from __future__ import annotations

from pathlib import Path

import rubiks_cfop as cube

FIGURES = {
    "net-solved.tex": cube.Cube.solved(),
    "net-scrambled.tex": cube.Cube.solved().apply_sequence("R U R' U' F2"),
}

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "figures"


def render(state: cube.Cube) -> str:
    """Return the tabular rows for one cube state."""
    layout = cube.net_layout(state)
    rows = []
    for row in layout.colors:
        cells = [
            r"\cubeblank" if color is None else rf"\cubecell{{{color.value}}}" for color in row
        ]
        rows.append(" & ".join(cells) + r" \\")
    return "\n".join(rows) + "\n"


def main() -> None:
    """Write every figure."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, state in FIGURES.items():
        (OUTPUT_DIR / name).write_text(render(state), encoding="utf-8")
        print(f"wrote {name}")


if __name__ == "__main__":
    main()

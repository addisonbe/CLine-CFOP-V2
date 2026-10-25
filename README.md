# rubiks-cfop

A **headless engine** that generates WCA scrambles for the 3x3x3 Rubik's Cube and
solves them with the **CFOP** method (Cross → F2L → OLL → PLL), plus a thin CLI
adapter.  The cube is represented with **Kociemba's facelet notation** and the
known algorithms live in **JSON lookup tables**.

The engine is designed to be embedded: it performs no I/O, has no third-party
runtime dependencies and returns structured, JSON-serializable results, so a GUI
(or a web front-end) can drive it directly.

## Manual

A full user manual, written in LaTeX, lives in [`manual/`](manual/README.md): it
covers installation, the command line reference, how to read the output, the
notation, how each stage is solved, the JSON lookup tables and the Python API, plus
an appendix setting out the plan for a graphical interface.

```bash
cd manual && latexmk -pdf main.tex
```

## Requirements

* Python **3.13** (managed by [uv](https://docs.astral.sh/uv/): `uv python install 3.13`)
* Runtime dependencies: **none**

## Quickstart

```bash
uv sync                 # create the venv, install dev tooling
scripts/check.sh        # the stage gate: ruff format + ruff check + pytest
```

## Conventions

* **Cube representation** — Kociemba facelet order
  `U1..U9 R1..R9 F1..F9 D1..D9 L1..L9 B1..B9`; the solved cube is
  `UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB`.
* **Moves** — WCA notation (Regulation 12a): face moves `U D L R F B`, wide moves
  `Uw Dw Lw Rw Fw Bw` (`2Rw` ≡ `Rw`), rotations `x y z`, each with `'` and `2`.
  Slice moves `M E S` are supported as a documented extension because many
  published OLL/PLL algorithms use them.
* **Colors** — standard scheme, white up / green front (WCA Regulation 4d1):
  `U` white, `R` red, `F` green, `D` yellow, `L` orange, `B` blue.
* **Cross** — always solved into the **bottom layer**; for a white cross the
  upper layer is therefore yellow.

### Two levels of cube model

| Level | What it is | Used for |
|---|---|---|
| `Cube` | The 54 sticker colors (the display), handling every move including rotations | everything the user sees, all move sequences, rendering |
| `CubieCube` | 8 corners and 12 edges with orientations, relative to the centers | the cube's algebraic invariants and the solvers' piece reasoning |

Whole cube rotations move the centers, so they change the *display*. `Cube.normalized()`
undoes such a rotation to give the canonical state, and `CubieCube.from_facelets`
normalizes before projecting — which means a rotated cube projects onto exactly the
same cubie state as its unrotated equivalent. Wide and slice moves are not elements
of the cubie group (they move the centers); the cubie level rejects them explicitly
and points at `Cube`.

### Scrambles

`generate_scramble()` defaults to **random-state** scrambles, which is what WCA
Regulation 4b3 requires for the 3x3x3: a uniformly random state, solved to obtain
the scramble.  The result is 20 to 22 moves, in the range of the official TNoodle
scrambles.  `style="random-move"` gives a filtered random-move sequence instead,
which is instant but *not* WCA-legal for the 3x3x3 (4b3e permits random-move only
for 5x5x5 and larger).

The random-state generator solves the drawn state with a Kociemba style
**two-phase solver** (`rubiks_cfop.solver`), which doubles as an independent oracle
that the CFOP pipeline is checked against.  Building its tables takes about 10
seconds of CPU, so they are built lazily on first use and cached for the life of
the process; a GUI should call `rubiks_cfop.preload()` on a background thread at
startup.  Generating a scramble afterwards takes well under a second on average.

Scrambles are deterministic for a given `seed`, and the seed is always recorded in
the result, so any scramble can be reproduced or shared.

## Engine contract

* no output on `stdout`/`stderr`, no environment access, no `sys.argv` reads,
* no mutable global state — solvers are reusable and thread-safe,
* long searches are cooperatively cancelable and support timeouts,
* every result is a dataclass with `to_dict()`/`from_dict()` and validates
  against the versioned JSON schema in `schemas/`.

## Usage

### Command line

```bash
# solve a scramble you were given
uv run rubiks-cfop --scramble "R U R' U' F2 D L2 B'"

# generate a random-state (WCA 4b3) scramble and solve it
uv run rubiks-cfop --random --seed 42

# pick the cross, list the six options first, and get JSON for a GUI
uv run rubiks-cfop --scramble "R U R' U'" --cross white --cross-options
uv run rubiks-cfop --scramble "R U R' U'" --json
```

The output starts with the unfolded cube of the scramble, drawn with real colors,
then lists the solution exactly as CFOP produces it:

```
         Top
        ⬜️⬜️🟧
        ⬜️⬜️🟩
        🟥🟨🟨
 Left   Front   Right    Back
🟦🟧⬜️  🟩🟩🟩  🟧🟥⬜️  🟦🟥🟥
🟧🟧🟦  ⬜️🟩🟩  🟧🟥🟥  🟦🟦🟦
🟦🟦🟦  🟧🟧🟥  🟨🟩🟩  🟧🟥🟥
         Down
        🟨🟨🟩
        🟨🟨⬜️
        🟨🟨⬜️

Orientation: none
Cross color: yellow (bottom layer)
Scramble: R U R' U' F2 D

Cross: D' F2
F2L1: R' F R F'
F2L2: (none)
F2L3: (none)
F2L4: (none)
OLL (37): F R' F' R U R U' R'
PLL (skip): (none)

Total: 14 moves
```

`--no-color` draws emoji squares instead of ANSI truecolor so the output also reads
well when piped into a file.

### Desktop interface

```bash
uv run rubiks-cfop-gui                       # or: uv run python -m rubiks_cfop.gui
uv run rubiks-cfop-gui --scramble "R U R' U'" --cross white
```

A Tkinter window (standard library only, so no extra dependency) with:

* a scramble bar that accepts a WCA scramble or a 54 letter facelet string, a
  random scramble button with style and seed, and a cross color picker;
* the unfolded net in the standard colors, laid out as the traditional cross;
* the solution table, one row per stage, which jumps to the end of that stage;
* a player that steps through the solution one move at a time (buttons, or the
  arrow keys, Home, End and Space).

Solving and scramble generation run on worker threads, so the window never freezes.
The code is split into a toolkit-free view-model (`gui/viewmodel.py`), the net
layout drawn through a painter interface (`gui/painter.py`) and the Tk window
(`gui/app.py`). The plan for a future 3D view is in
[`docs/gui-3d-plan.md`](docs/gui-3d-plan.md).

### As a library

```python
import rubiks_cfop as cube

scramble = cube.generate_scramble(seed=42)  # WCA random-state scramble
solution = cube.solve_cube(scramble.state)  # CFOP
print(solution.to_dict())  # JSON-ready payload
for stage in solution.stages:
    print(stage.label, stage.text)

print(cube.render_emoji(cube.net_layout(scramble.state)))
```

## Known limitations

* **F2L speed** — the 41-case table only covers configurations whose pieces are in
  the U layer or the target slot; everything else is inserted by a search, which is
  correct but takes a second or two per pair. A complete pair table (or a
  two-phase extraction step) would remove that cost.
* **Last-layer table coverage** — the OLL/PLL tables are built from one published
  algorithm per case and verified exhaustively; a handful of states rely on the
  pipeline's two-phase rescue rather than a named algorithm.
* **Slices and rotations in algorithms** — stages that use them re-orient the
  display afterwards so the cube stays "cross down"; the solution stays valid but
  the move list contains rotations.

## Development stages

Each stage is gated: `ruff format --check`, `ruff check`, the full test suite and a
coverage floor must pass before the stage is committed.

| Stage | Scope | Status |
|---|---|---|
| 0 | Bootstrap, tooling, package skeleton, engine contract tests | ✅ |
| 1 | Cube core: facelets, 18 face + 18 wide + 9 rotation moves, notation | ✅ |
| 2a | Random-move scrambler | ✅ |
| 2b | Random-state scrambler (WCA 4b3) via two-phase solver | ✅ |
| 3 | Unfolded net renderer (real colors, structured layout) | ✅ |
| 4 | Search infrastructure (BFS distance tables, pruning, move filters) | ✅ |
| 5 | Cross solver (optimal, chosen color or best of six) | ✅ |
| 6 | F2L: 41-case JSON table + verified search fallback | ✅ (search is slow, see notes) |
| 7 | OLL: 57 numbered cases, JSON table, exhaustive recognition proof | ✅ |
| 8 | PLL: 21 named cases, JSON table, exhaustive recognition proof | ✅ |
| 9 | CFOP pipeline + engine façade (`solve_cube`, JSON payload) | ✅ |
| 10 | CLI (`rubiks-cfop`) with net, stages, `--json` | ✅ |
| 11 | Docs, packaging (tables ship inside the package), final validation | ✅ |
| 12 | Desktop GUI (Tkinter): net, solution table, move-by-move player | ✅ |

# rubiks-cfop

A **headless engine** that generates WCA scrambles for the 3x3x3 Rubik's Cube and
solves them with the **CFOP** method (Cross → F2L → OLL → PLL), plus a thin CLI
adapter.  The cube is represented with **Kociemba's facelet notation** and the
known algorithms live in **JSON lookup tables**.

The engine is designed to be embedded: it performs no I/O, has no third-party
runtime dependencies and returns structured, JSON-serializable results, so a GUI
(or a web front-end) can drive it directly.

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
* **Colours** — standard scheme, white up / green front (WCA Regulation 4d1):
  `U` white, `R` red, `F` green, `D` yellow, `L` orange, `B` blue.
* **Cross** — always solved into the **bottom layer**; for a white cross the
  upper layer is therefore yellow.

### Two levels of cube model

| Level | What it is | Used for |
|---|---|---|
| `Cube` | The 54 sticker colours (the display), handling every move including rotations | everything the user sees, all move sequences, rendering |
| `CubieCube` | 8 corners and 12 edges with orientations, relative to the centres | the cube's algebraic invariants and the solvers' piece reasoning |

Whole cube rotations move the centres, so they change the *display*. `Cube.normalized()`
undoes such a rotation to give the canonical state, and `CubieCube.from_facelets`
normalises before projecting — which means a rotated cube projects onto exactly the
same cubie state as its unrotated equivalent. Wide and slice moves are not elements
of the cubie group (they move the centres); the cubie level rejects them explicitly
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
* long searches are cooperatively cancellable and support timeouts,
* every result is a dataclass with `to_dict()`/`from_dict()` and validates
  against the versioned JSON schema in `schemas/`.

## Development stages

Each stage is gated: `ruff format --check`, `ruff check`, the full test suite and a
coverage floor must pass before the stage is committed.

| Stage | Scope | Status |
|---|---|---|
| 0 | Bootstrap, tooling, package skeleton, engine contract tests | ✅ |
| 1 | Cube core: facelets, 18 face + 18 wide + 9 rotation moves, notation | ✅ |
| 2a | Random-move scrambler | ✅ |
| 2b | Random-state scrambler (WCA 4b3) via two-phase solver | ✅ |
| 3 | Unfolded net renderer (real colours, structured layout) | ✅ |
| 4 | Search infrastructure (BFS distance tables, pruning, move filters) | ✅ |
| 5 | Cross solver (optimal, chosen colour or best of six) | ✅ |
| 6 | F2L (JSON table + verified search fallback) | ⏳ |
| 7 | OLL (57 numbered cases + 2-look fallback) | ⏳ |
| 8 | PLL (21 named cases + 2-look fallback) | ⏳ |
| 9 | Engine façade, JSON schema, GUI-readiness contract | ⏳ |
| 10 | CLI (`rubiks-cfop`) | ⏳ |
| 11 | Docs, packaging, final validation | ⏳ |

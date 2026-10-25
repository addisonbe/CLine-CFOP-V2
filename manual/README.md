# The user manual

The manual is written in LaTeX and built from `main.tex`.

## Building

```bash
cd manual
latexmk -pdf main.tex          # or: pdflatex main && pdflatex main
```

`latexmk` runs LaTeX as many times as the table of contents and cross references
need.  The result is `main.pdf`.

Only standard packages are used: `geometry`, `xcolor` (with `table`), `booktabs`,
`longtable`, `enumitem`, `listings`, `fancyhdr`, `hyperref`, `amsmath`, plus the
`lmodern` fonts.  A `texlive-latex-recommended` installation covers them.

## Layout

```
manual/
  main.tex                 preamble, title page, includes
  sections/                one file per chapter
  appendix/gui-plan.tex    the plan for the graphical interface
  figures/net-*.tex        cube nets, generated from the engine
  tools/make_figures.py    regenerates the figures
  README.md                this file
```

## Figures

The net figures are not drawn by hand: they are produced by the engine's own
renderer, so the pictures in the manual always match what the program prints.

```bash
uv run python manual/tools/make_figures.py
```

This rewrites `manual/figures/net-solved.tex` and `net-scrambled.tex`.  Each cell
becomes `\cubecell{<color>}` (a colored square) or `\cubeblank`, using the palette
defined in `main.tex` -- the same six RGB values as `DEFAULT_PALETTE` in the engine.

## Note on the toolchain

The development sandbox used for this project has no TeX distribution, so the
sources were validated structurally (every `\input` resolves, environments balance,
braces balance, only ASCII characters are used, every color is defined) rather than
by a compile.  Building with `latexmk` above is the real check.

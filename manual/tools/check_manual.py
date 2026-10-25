"""Structural checks for the manual's LaTeX sources.

The development sandbox has no TeX distribution, so this script does what can be
done without one: it makes sure the sources are internally consistent, that every
included file exists, that environments and braces balance, that only ASCII is used
(so pdflatex with T1/lmodern cannot trip over a glyph), and that every color and
label referenced is defined.

It is a smoke test, not a substitute for compiling: `latexmk -pdf main.tex` remains
the real check.  Run with::

    uv run python manual/tools/check_manual.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWN_ENVIRONMENTS = {
    "abstract",
    "center",
    "description",
    "document",
    "enumerate",
    "figure",
    "itemize",
    "longtable",
    "lstlisting",
    "tabular",
}

INPUT_RE = re.compile(r"\\input\{([^}]*)\}")
ENV_BEGIN_RE = re.compile(r"\\begin\{([^}]*)\}")
ENV_END_RE = re.compile(r"\\end\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
REF_RE = re.compile(r"\\ref\{([^}]*)\}")
COLOR_USE_RE = re.compile(r"\\cubecell\{([^}]*)\}")
COLOR_DEF_RE = re.compile(r"\\definecolor\{([^}]*)\}")


def strip_comments(text: str) -> str:
    """Remove LaTeX comments, keeping escaped percent signs."""
    return re.sub(r"(?<!\\)%.*", "", text)


def walk() -> list[Path]:
    """Return every .tex file of the manual, in a stable order."""
    return sorted(
        [
            ROOT / "main.tex",
            *ROOT.glob("sections/*.tex"),
            *ROOT.glob("appendix/*.tex"),
            *ROOT.glob("figures/*.tex"),
        ]
    )


def check(path: Path, colors: set[str], labels: set[str], problems: list[str]) -> None:
    """Check one file, collecting problems."""
    raw = path.read_text(encoding="utf-8")
    name = path.relative_to(ROOT)

    non_ascii = sorted({char for char in raw if ord(char) > 127})
    if non_ascii:
        problems.append(f"{name}: non-ASCII characters {non_ascii}")

    text = strip_comments(raw)

    if text.count("{") != text.count("}"):
        problems.append(
            f"{name}: unbalanced braces ({text.count('{')} open, {text.count('}')} close)"
        )

    opened = ENV_BEGIN_RE.findall(text)
    closed = ENV_END_RE.findall(text)
    if sorted(opened) != sorted(closed):
        problems.append(f"{name}: environments do not balance ({opened} vs {closed})")
    for environment in opened:
        if environment not in KNOWN_ENVIRONMENTS:
            problems.append(f"{name}: unknown environment {environment!r}")

    for target in INPUT_RE.findall(text):
        if target.startswith("#"):  # a macro parameter, not a file
            continue
        if not (ROOT / target).is_file() and not (ROOT / f"{target}.tex").is_file():
            problems.append(f"{name}: \\input{{{target}}} does not exist")

    for color in COLOR_USE_RE.findall(text):
        if color not in colors:
            problems.append(f"{name}: color {color!r} is not defined")

    labels.update(LABEL_RE.findall(text))


def main() -> int:
    """Run every check and report."""
    problems: list[str] = []
    colors: set[str] = set()
    labels: set[str] = set()

    main_tex = (ROOT / "main.tex").read_text(encoding="utf-8")

    # Colors are defined in the preamble, and only there.
    for color in COLOR_DEF_RE.findall(main_tex):
        colors.add(color)
    for environment in ENV_BEGIN_RE.findall(strip_comments(main_tex)):
        if environment not in KNOWN_ENVIRONMENTS:
            problems.append(f"main.tex: unknown environment {environment!r}")

    files = walk()
    for path in files:
        check(path, colors, labels, problems)

    references: set[str] = set()
    for path in files:
        references.update(REF_RE.findall(strip_comments(path.read_text(encoding="utf-8"))))
    for reference in sorted(references - labels):
        problems.append(f"\\ref{{{reference}}} has no matching \\label")

    if "\\begin{document}" not in main_tex or "\\end{document}" not in main_tex:
        problems.append("main.tex: missing the document environment")

    included = {
        target.removesuffix(".tex") for target in INPUT_RE.findall(strip_comments(main_tex))
    }
    for path in ROOT.glob("sections/*.tex"):
        if f"sections/{path.stem}" not in included:
            problems.append(f"{path.relative_to(ROOT)} is never included")
    for path in ROOT.glob("appendix/*.tex"):
        if f"appendix/{path.stem}" not in included:
            problems.append(f"{path.relative_to(ROOT)} is never included")

    sections = sum(
        len(re.findall(r"\\section\{", strip_comments(path.read_text(encoding="utf-8"))))
        for path in files
    )
    print(
        f"checked {len(files)} files, {len(colors)} colors, {len(labels)} labels, "
        f"{sections} sections"
    )
    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(" -", problem)
        return 1
    print("no structural problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())

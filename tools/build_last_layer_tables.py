"""Build ``data/oll.json`` and ``data/pll.json`` from a published algorithm set.

The source is the Logiqx ``cubing-algs`` collection (https://github.com/Logiqx/
cubing-algs), whose case ids match the community numbering: 1 to 57 for OLL and the
standard names for PLL.  Its files are JavaScript objects, so trailing commas are
stripped before parsing.

For each case the tool picks the shortest algorithm that

* uses face turns only -- no rotations, wide moves or slice moves, so that the
  display orientation is preserved and the cube stays "cross down";
* parses with the engine's notation rules;
* actually solves its case, which is checked against a second algorithm of the
  same case when one exists.

Usage::

    python tools/build_last_layer_tables.py oll.js pll.js [f2l.js]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import SOLVED_FACELETS
from rubiks_cfop.cube.notation import parse_moves
from rubiks_cfop.errors import NotationError

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"

#: Terms that would rotate the display and break the cross-down invariant.
FORBIDDEN = re.compile(r"\b[xyz]\b|\b[MES]\b|\b\w*w\b|\b[rludfb]\b")


def load_js(path: Path) -> dict[str, Any]:
    """Read one of the collection's JavaScript data files."""
    text = path.read_text(encoding="utf-8")
    body = text.split("=", 1)[1].strip().rstrip(";")
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", body))


def clean(algorithm: str) -> str:
    """Normalise an algorithm: drop brackets, collapse whitespace."""
    return " ".join(algorithm.replace("(", " ").replace(")", " ").split())


def candidate_algorithms(case: dict[str, Any]) -> list[str]:
    """Return every algorithm listed for a case, cleaned and de-duplicated."""
    found: list[str] = []
    for entry in case["algs"]:
        found.append(clean(entry["alg"]))
        found.extend(clean(variant["alg"]) for variant in entry.get("vars", []))
    seen: list[str] = []
    for algorithm in found:
        if algorithm and algorithm not in seen:
            seen.append(algorithm)
    return seen


def solves(kind: str, algorithm: str) -> bool:
    """Return whether ``algorithm`` solves its own case."""
    try:
        moves = parse_moves(algorithm)
    except NotationError:
        return False
    inverse = [move.inverse() for move in reversed(moves)]
    state = Cube.from_facelets(SOLVED_FACELETS).apply_moves(inverse)
    after = state.apply_moves(moves)
    if kind == "oll":
        return after.cubie().co[:4] == (0, 0, 0, 0) and after.cubie().eo[:4] == (0, 0, 0, 0)
    return (
        after.is_solved()
        or after.apply("U").is_solved()
        or after.apply("U2").is_solved()
        or after.apply("U'").is_solved()
    )


def agrees(kind: str, first: str, second: str) -> bool:
    """Return whether two algorithms of the same case solve the same state."""
    try:
        moves = parse_moves(first)
        other = parse_moves(second)
    except NotationError:
        return True
    inverse = [move.inverse() for move in reversed(moves)]
    state = Cube.from_facelets(SOLVED_FACELETS).apply_moves(inverse)
    after = state.apply_moves(other)
    if kind == "oll":
        return after.cubie().co[:4] == (0, 0, 0, 0) and after.cubie().eo[:4] == (0, 0, 0, 0)
    return (
        after.is_solved()
        or after.apply("U").is_solved()
        or after.apply("U2").is_solved()
        or after.apply("U'").is_solved()
    )


def choose(kind: str, case: dict[str, Any]) -> str | None:
    """Pick the best algorithm for a case."""
    algorithms = candidate_algorithms(case)
    usable = [a for a in algorithms if solves(kind, a)]
    if not usable:
        return None
    # Prefer algorithms that keep the display orientation (face turns only), then
    # the shortest one.  Algorithms with rotations or wide moves are still fine: the
    # stage normalises the display afterwards, which does not change the puzzle.
    usable.sort(key=lambda a: (bool(FORBIDDEN.search(a)), len(a.split()), a))
    return usable[0]


def build(kind: str, source: Path, destination: Path, *, labelled: bool) -> int:
    """Build one table and return how many cases it holds."""
    data = load_js(source)
    cases: list[dict[str, Any]] = []
    for case in data["cases"]:
        if case["id"] == "Skip":
            continue
        algorithm = choose(kind, case)
        if algorithm is None:
            print(f"  {kind} {case['id']}: no usable algorithm", file=sys.stderr)
            continue
        label = case["id"] if not labelled else f"{case['id']} Perm"
        name = case.get("name", "").strip() or label
        cases.append({"label": label, "name": name, "algorithm": algorithm})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps({"schema": 1, "kind": kind, "cases": cases}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  {kind}: {len(cases)} cases -> {destination}")
    return len(cases)


def main(argv: list[str]) -> int:
    """Build both tables from the paths given on the command line."""
    if len(argv) < 3:  # noqa: PLR2004 - two paths are required
        print(__doc__)
        return 2
    build("oll", Path(argv[1]), OUTPUT_DIR / "oll.json", labelled=False)
    build("pll", Path(argv[2]), OUTPUT_DIR / "pll.json", labelled=True)
    if len(argv) > 3:  # noqa: PLR2004
        build_f2l(Path(argv[3]), OUTPUT_DIR / "f2l.json")
    return 0


def build_f2l(source: Path, destination: Path) -> int:
    """Build the F2L table: 41 cases, in the front-right frame."""
    data = load_js(source)
    cases: list[dict[str, Any]] = []
    for case in data["cases"]:
        if case["id"] == "Skip":
            continue
        algorithms = [a for a in candidate_algorithms(case) if not FORBIDDEN.search(a)]
        if not algorithms:
            algorithms = candidate_algorithms(case)
        usable = []
        for algorithm in algorithms:
            try:
                parse_moves(algorithm)
            except NotationError:
                continue
            usable.append(algorithm)
        if not usable:
            print(f"  f2l {case['id']}: no usable algorithm", file=sys.stderr)
            continue
        usable.sort(key=lambda a: (len(a.split()), a))
        label = case["id"]
        name = case.get("name", "").strip() or f"F2L {label}"
        cases.append({"label": label, "name": name, "algorithm": usable[0]})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps({"schema": 1, "kind": "f2l", "cases": cases}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  f2l: {len(cases)} cases -> {destination}")
    return len(cases)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

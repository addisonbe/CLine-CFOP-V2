"""The command line interface: scramble, solve, and print the result.

The CLI is a thin adapter over the engine.  It owns everything the engine
deliberately does not: parsing arguments, deciding whether the terminal supports
colour, writing to stdout and choosing an exit code.

Output starts with the unfolded cube of the scramble, drawn with real colours, then
lists the solution stage by stage::

    Scramble: R U R' U'
    Cross: D' R2
    F2L1: U R U' R'
    F2L2: ...
    F2L3: ...
    F2L4: ...
    OLL (27): R U R' U R U2 R'
    PLL (T Perm): R U R' U' R' F R2 U' R' U' R U R' F'
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import Color
from rubiks_cfop.errors import RubiksError
from rubiks_cfop.render.net import net_layout, render_ansi, render_emoji
from rubiks_cfop.scramble.random_move import random_move_scramble
from rubiks_cfop.scramble.random_state import random_state_scramble
from rubiks_cfop.solver.cfop import Solution, cross_options, solve_cube

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["build_parser", "main", "render_solution"]

#: Exit code used when the input cannot be understood or solved.
FAILURE: int = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for ``rubiks-cfop``."""
    parser = argparse.ArgumentParser(
        prog="rubiks-cfop",
        description="Generate WCA scrambles and solve the 3x3x3 cube with CFOP.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--scramble",
        metavar="MOVES",
        help="a scramble in WCA notation, for example \"R U R' U' F2\"",
    )
    source.add_argument(
        "--facelets",
        metavar="STATE",
        help="a 54 character Kociemba facelet string instead of a scramble",
    )
    source.add_argument(
        "--random",
        action="store_true",
        help="generate a scramble (the default when no scramble is given)",
    )
    parser.add_argument(
        "--scramble-style",
        choices=("random-state", "random-move"),
        default="random-state",
        help="how --random builds its scramble (default: random-state, which is WCA 4b3)",
    )
    parser.add_argument("--seed", type=int, default=None, help="seed for a generated scramble")
    parser.add_argument(
        "--cross",
        choices=("best", *[color.value for color in Color]),
        default="best",
        help="the cross colour, or best for the shortest of the six (default)",
    )
    parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        default=None,
        help="force colour output (default: colour when stdout is a terminal)",
    )
    parser.add_argument(
        "--no-color",
        dest="color",
        action="store_false",
        help="draw the net with emoji squares instead of ANSI colours",
    )
    parser.add_argument("--json", action="store_true", help="print the machine-readable payload")
    parser.add_argument(
        "--cross-options",
        action="store_true",
        help="list the six crosses with their lengths before solving",
    )
    return parser


def _resolve_cube(args: argparse.Namespace) -> tuple[Cube, str | None, str | None]:
    """Return the cube to solve, the scramble text and the generated scramble."""
    if args.facelets:
        return Cube.from_facelets(args.facelets), None, None
    if args.scramble:
        cube = Cube.solved().apply_scramble(args.scramble)
        return cube, args.scramble, None
    if args.scramble_style == "random-move":
        scramble = random_move_scramble(seed=args.seed)
    else:
        scramble = random_state_scramble(seed=args.seed)
    return scramble.state, scramble.text, scramble.text


def render_solution(solution: Solution, *, color: bool) -> str:
    """Render a solution: the net first, then the scramble and the stages."""
    layout = net_layout(solution.initial)
    net = render_ansi(layout) if color else render_emoji(layout)
    rotation = "".join(move.name for move in solution.rotation) or "none"
    lines = [
        net,
        "",
        f"Orientation: {rotation}",
        f"Cross colour: {solution.cross_color.value} (bottom layer)",
    ]
    if solution.scramble:
        lines.append(f"Scramble: {solution.scramble}")
    lines.append("")
    lines.extend(f"{stage.label}: {stage.text or '(none)'}" for stage in solution.stages)
    lines.append("")
    lines.append(f"Total: {solution.total_moves} moves")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    use_color = args.color if args.color is not None else sys.stdout.isatty()

    try:
        cube, scramble_text, generated = _resolve_cube(args)
        if args.cross_options:
            for option in cross_options(cube):
                print(f"  {option.color.value:7s} {option.length} moves")
        solution = solve_cube(
            cube,
            cross=args.cross,
            scramble=scramble_text or generated,
        )
    except RubiksError as error:
        print(f"error: {error}", file=sys.stderr)
        return FAILURE

    if args.json:
        print(json.dumps(solution.to_dict(), indent=2))
        return 0
    print(render_solution(solution, color=use_color))
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())

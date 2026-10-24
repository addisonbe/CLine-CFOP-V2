"""The unfolded cube net: a structured layout plus text serializers.

The net is the usual cross shape, with the front face in the middle::

          U
    L  F  R  B
          D

so the layout is nine rows of twelve cells, of which 54 are used.  Each face is
laid out in reading order, matching the facelet order inside the face, which makes
the cell-to-facelet mapping trivial to verify.

:class:`NetLayout` holds colours, not letters, so a GUI can render the cube with
its own palette; the text serializers below are for terminals.  ANSI truecolor is
used by default, with emoji squares as a fallback for terminals without colour
support.  Letters are available too, but only on request: the engine's output is
supposed to show real colours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.facelets import COLOR_FACE, FACE_ORDER, Color, Face

if TYPE_CHECKING:
    from rubiks_cfop.cube.cube import Cube

__all__ = [
    "DEFAULT_PALETTE",
    "EMPTY_CELL",
    "NET_COLUMNS",
    "NET_ORIGINS",
    "NET_ROWS",
    "NetLayout",
    "net_layout",
    "render_ansi",
    "render_emoji",
    "render_letters",
    "render_plain",
]

#: Where each face starts in the net, as ``(row, column)`` of its top-left cell.
NET_ORIGINS: Final[dict[Face, tuple[int, int]]] = {
    Face.U: (0, 3),
    Face.L: (3, 0),
    Face.F: (3, 3),
    Face.R: (3, 6),
    Face.B: (3, 9),
    Face.D: (6, 3),
}

NET_ROWS: Final = 9
NET_COLUMNS: Final = 12
FACE_SIZE: Final = 3

#: Marker for a cell of the layout that no face covers.
EMPTY_CELL: Final = -1

#: The standard cubing colours (WCA Regulation 4d1 scheme), as RGB triples.
DEFAULT_PALETTE: Final[dict[Color, tuple[int, int, int]]] = {
    Color.WHITE: (255, 255, 255),
    Color.RED: (196, 30, 58),
    Color.GREEN: (0, 158, 96),
    Color.YELLOW: (255, 213, 0),
    Color.ORANGE: (255, 88, 0),
    Color.BLUE: (0, 81, 186),
}

#: Emoji square per colour, for terminals without truecolor support.
EMOJI: Final[dict[Color, str]] = {
    Color.WHITE: "\u2b1c",
    Color.RED: "\U0001f7e5",
    Color.GREEN: "\U0001f7e9",
    Color.YELLOW: "\U0001f7e8",
    Color.ORANGE: "\U0001f7e7",
    Color.BLUE: "\U0001f7e6",
}

_ANSI_TEMPLATE: Final = "\x1b[48;2;{red};{green};{blue}m{block}\x1b[0m"
_ANSI_BLOCK: Final = "  "


@dataclass(frozen=True, slots=True)
class NetLayout:
    """The unfolded cube as a grid of colours.

    Attributes:
        colors: ``colors[row][column]`` is the colour of a cell, or ``None`` where
            no face covers the net.
        facelets: ``facelets[row][column]`` is the Kociemba facelet index drawn in
            that cell, or :data:`EMPTY_CELL`.
    """

    colors: tuple[tuple[Color | None, ...], ...]
    facelets: tuple[tuple[int, ...], ...]

    def cell(self, row: int, column: int) -> Color | None:
        """Return the colour of a cell, or ``None`` outside the net.

        Raises:
            IndexError: If the coordinates are outside the grid.
        """
        return self.colors[row][column]

    def facelet(self, row: int, column: int) -> int:
        """Return the facelet index of a cell, or :data:`EMPTY_CELL`."""
        return self.facelets[row][column]

    def face_colors(self, face: Face | str) -> tuple[tuple[Color, ...], ...]:
        """Return the three by three colours of one face, in reading order."""
        resolved = Face(face)
        row0, column0 = NET_ORIGINS[resolved]
        return tuple(
            tuple(
                self._require(self.colors[row0 + row][column0 + column])
                for column in range(FACE_SIZE)
            )
            for row in range(FACE_SIZE)
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view: six faces of colour names."""
        return {
            "net": [
                [None if color is None else color.value for color in row] for row in self.colors
            ],
            "faces": {
                face.value: [[color.value for color in row] for row in self.face_colors(face)]
                for face in FACE_ORDER
            },
        }

    @staticmethod
    def _require(color: Color | None) -> Color:
        """Return a colour, asserting that the cell is inside the net."""
        if color is None:  # pragma: no cover - geometry guarantees a colour here
            raise AssertionError("cell outside the net")
        return color


def _build_layout(cube: Cube) -> NetLayout:
    """Map the 54 facelets of ``cube`` onto the net grid."""
    colors: list[list[Color | None]] = [[None] * NET_COLUMNS for _ in range(NET_ROWS)]
    facelets: list[list[int]] = [[EMPTY_CELL] * NET_COLUMNS for _ in range(NET_ROWS)]
    cube_colors = cube.colors()
    for face in FACE_ORDER:
        row0, column0 = NET_ORIGINS[face]
        offset = FACE_ORDER.index(face) * FACE_SIZE * FACE_SIZE
        for row in range(FACE_SIZE):
            for column in range(FACE_SIZE):
                index = offset + row * FACE_SIZE + column
                colors[row0 + row][column0 + column] = cube_colors[index]
                facelets[row0 + row][column0 + column] = index
    return NetLayout(
        colors=tuple(tuple(row) for row in colors),
        facelets=tuple(tuple(row) for row in facelets),
    )


def net_layout(cube: Cube) -> NetLayout:
    """Return the unfolded net of ``cube`` as a structured layout."""
    return _build_layout(cube)


def render_ansi(
    layout: NetLayout,
    *,
    palette: dict[Color, tuple[int, int, int]] | None = None,
    block: str = _ANSI_BLOCK,
) -> str:
    """Render a layout as coloured blocks, using 24 bit ANSI background colours.

    Args:
        layout: The net to render.
        palette: Colour to RGB mapping; defaults to :data:`DEFAULT_PALETTE`.
        block: The characters drawn inside each cell.

    Returns:
        The rendering, nine lines of twelve cells.
    """
    colors = DEFAULT_PALETTE if palette is None else palette
    lines: list[str] = []
    for row in layout.colors:
        cells: list[str] = []
        for color in row:
            if color is None:
                cells.append(" " * len(block))
                continue
            red, green, blue = colors[color]
            cells.append(_ANSI_TEMPLATE.format(red=red, green=green, blue=blue, block=block))
        lines.append("".join(cells).rstrip())
    return "\n".join(lines)


def render_emoji(layout: NetLayout) -> str:
    """Render a layout with coloured emoji squares, for terminals without colour."""
    lines: list[str] = []
    for row in layout.colors:
        cells = "".join(EMOJI[color] if color is not None else "  " for color in row)
        lines.append(cells.rstrip())
    return "\n".join(lines)


def render_letters(layout: NetLayout) -> str:
    """Render a layout as colour letters, for logs and diffs.

    This is deliberately not the default: the engine's output shows real colours.
    """
    lines: list[str] = []
    for row in layout.colors:
        cells = "".join("  " if color is None else f"{COLOR_FACE[color].value} " for color in row)
        lines.append(cells.rstrip())
    return "\n".join(lines)


def render_plain(cube: Cube) -> str:
    """Render a cube's facelets, one face per line, for diagnostics."""
    return "\n".join(
        cube.facelets[index * FACE_SIZE * FACE_SIZE : (index + 1) * FACE_SIZE * FACE_SIZE]
        for index in range(len(FACE_ORDER))
    )

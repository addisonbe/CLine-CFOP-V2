"""The unfolded cube net: a structured layout plus text serializers.

The net is the usual cross shape, with the front face in the middle::

          U
    L  F  R  B
          D

so the layout is nine rows of twelve cells, of which 54 are used.  Each face is
laid out in reading order, matching the facelet order inside the face, which makes
the cell-to-facelet mapping trivial to verify.

:class:`NetLayout` holds colors, not letters, so a GUI can render the cube with
its own palette; the text serializers below are for terminals.  ANSI truecolor is
used by default, with emoji squares as a fallback for terminals without color
support.  Both draw each face as a separate block with its name above it; in the
ANSI rendering, thin black lines also separate the stickers, like the plastic of a
real cube.  Letters are available too, but only on request: the engine's output is
supposed to show real colors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from rubiks_cfop.cube.facelets import COLOR_FACE, FACE_ORDER, Color, Face

if TYPE_CHECKING:
    from collections.abc import Callable

    from rubiks_cfop.cube.cube import Cube

__all__ = [
    "DEFAULT_PALETTE",
    "EMPTY_CELL",
    "FACE_LABELS",
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

#: The standard cubing colors (WCA Regulation 4d1 scheme), as RGB triples.
DEFAULT_PALETTE: Final[dict[Color, tuple[int, int, int]]] = {
    Color.WHITE: (255, 255, 255),
    Color.RED: (196, 30, 58),
    Color.GREEN: (0, 158, 96),
    Color.YELLOW: (255, 213, 0),
    Color.ORANGE: (255, 88, 0),
    Color.BLUE: (0, 81, 186),
}

#: The color of the lines between stickers in the ANSI rendering.
SEPARATOR_RGB: Final = (0, 0, 0)

#: Emoji square per color, for terminals without truecolor support.  White is the
#: only square outside the "colored squares" block, and some terminals draw it as
#: a text symbol; the variation selector asks for the emoji glyph instead.
EMOJI: Final[dict[Color, str]] = {
    Color.WHITE: "\u2b1c\ufe0f",
    Color.RED: "\U0001f7e5",
    Color.GREEN: "\U0001f7e9",
    Color.YELLOW: "\U0001f7e8",
    Color.ORANGE: "\U0001f7e7",
    Color.BLUE: "\U0001f7e6",
}

#: The name written above each face in the text renderings.
FACE_LABELS: Final[dict[Face, str]] = {
    Face.U: "Top",
    Face.L: "Left",
    Face.F: "Front",
    Face.R: "Right",
    Face.B: "Back",
    Face.D: "Down",
}

# The text renderings draw the faces as separate blocks, band by band.
_BANDS: Final[tuple[tuple[Face | None, ...], ...]] = (
    (None, Face.U),
    (Face.L, Face.F, Face.R, Face.B),
    (None, Face.D),
)
_FACE_SPACING: Final = "  "
_EMOJI_WIDTH: Final = 2

_ANSI_RESET: Final = "\x1b[0m"
_ANSI_BACKGROUND: Final = "\x1b[48;2;{red};{green};{blue}m"
_ANSI_FOREGROUND: Final = "\x1b[38;2;{red};{green};{blue}m"
# Lower seven-eighths blocks: the sticker color fills the cell except for a thin
# strip at the top, where the black background shows as the line between rows.
_ANSI_BLOCK: Final = "▇▇"


@dataclass(frozen=True, slots=True)
class NetLayout:
    """The unfolded cube as a grid of colors.

    Attributes:
        colors: ``colors[row][column]`` is the color of a cell, or ``None`` where
            no face covers the net.
        facelets: ``facelets[row][column]`` is the Kociemba facelet index drawn in
            that cell, or :data:`EMPTY_CELL`.
    """

    colors: tuple[tuple[Color | None, ...], ...]
    facelets: tuple[tuple[int, ...], ...]

    def cell(self, row: int, column: int) -> Color | None:
        """Return the color of a cell, or ``None`` outside the net.

        Raises:
            IndexError: If the coordinates are outside the grid.
        """
        return self.colors[row][column]

    def facelet(self, row: int, column: int) -> int:
        """Return the facelet index of a cell, or :data:`EMPTY_CELL`."""
        return self.facelets[row][column]

    def face_colors(self, face: Face | str) -> tuple[tuple[Color, ...], ...]:
        """Return the three by three colors of one face, in reading order."""
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
        """Return a JSON-serializable view: six faces of color names."""
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
        """Return a color, asserting that the cell is inside the net."""
        if color is None:  # pragma: no cover - geometry guarantees a color here
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
    labels: bool = True,
) -> str:
    """Render a layout as colored blocks, using 24 bit ANSI colors.

    Each face is drawn as its own three by three block, with a gap between faces
    and, optionally, its name above it.  Each sticker is drawn in its color on a
    black background, with a black column between neighboring stickers and a thin
    black strip above each row, so the stickers read as separate squares.

    Args:
        layout: The net to render.
        palette: Color to RGB mapping; defaults to :data:`DEFAULT_PALETTE`.
        block: The characters drawn inside each cell, in the sticker's color.
        labels: Whether to write each face's name above it.

    Returns:
        The rendering: for each band of faces, a name line, then three sticker rows.
    """
    colors = DEFAULT_PALETTE if palette is None else palette
    background = _ANSI_BACKGROUND.format(
        red=SEPARATOR_RGB[0], green=SEPARATOR_RGB[1], blue=SEPARATOR_RGB[2]
    )
    gap = f"{background} {_ANSI_RESET}"

    def sticker(color: Color) -> str:
        red, green, blue = colors[color]
        foreground = _ANSI_FOREGROUND.format(red=red, green=green, blue=blue)
        return f"{background}{foreground}{block}{_ANSI_RESET}"

    def draw_row(row: tuple[Color, ...]) -> str:
        return gap + "".join(sticker(color) + gap for color in row)

    width = FACE_SIZE * (len(block) + 1) + 1
    return _render_faces(layout, draw_row, width, labels=labels)


def render_emoji(layout: NetLayout, *, labels: bool = True) -> str:
    """Render a layout with colored emoji squares, for terminals without color.

    The faces are laid out like :func:`render_ansi`: separate three by three blocks
    with a gap between them and, optionally, each face's name above it.
    """

    def draw_row(row: tuple[Color, ...]) -> str:
        return "".join(EMOJI[color] for color in row)

    return _render_faces(layout, draw_row, FACE_SIZE * _EMOJI_WIDTH, labels=labels)


def _render_faces(
    layout: NetLayout,
    draw_row: Callable[[tuple[Color, ...]], str],
    width: int,
    *,
    labels: bool,
) -> str:
    """Lay the six faces out as a cross of separate blocks.

    Args:
        layout: The net to render.
        draw_row: Draws one row of three stickers.
        width: The number of terminal columns ``draw_row`` fills.
        labels: Whether to write each face's name above it.
    """
    lines: list[str] = []
    for band in _BANDS:
        if labels:
            names = (
                " " * width if face is None else FACE_LABELS[face].center(width) for face in band
            )
            lines.append(_FACE_SPACING.join(names).rstrip())
        for row in range(FACE_SIZE):
            cells = (
                " " * width if face is None else draw_row(layout.face_colors(face)[row])
                for face in band
            )
            lines.append(_FACE_SPACING.join(cells).rstrip())
    return "\n".join(lines)


def render_letters(layout: NetLayout) -> str:
    """Render a layout as color letters, for logs and diffs.

    This is deliberately not the default: the engine's output shows real colors.
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

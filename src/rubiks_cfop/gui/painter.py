"""Drawing the unfolded net through a small painter interface.

The net is laid out here, once, against a :class:`Painter` protocol.  The window
passes a painter backed by a Tk canvas; the tests pass a recorder and assert the
rectangles cell for cell, without a screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from rubiks_cfop.cube.facelets import FACE_ORDER
from rubiks_cfop.render.net import (
    DEFAULT_PALETTE,
    FACE_SIZE,
    NET_COLUMNS,
    NET_ORIGINS,
    NET_ROWS,
    net_layout,
)

if TYPE_CHECKING:
    from rubiks_cfop.cube.cube import Cube
    from rubiks_cfop.cube.facelets import Color

__all__ = ["NetGeometry", "Painter", "hex_color", "paint_net"]

#: Color of the lines between stickers, and of the plastic behind them.
STICKER_OUTLINE: Final = "#111111"
LABEL_COLOR: Final = "#222222"


class Painter(Protocol):
    """What :func:`paint_net` needs from a drawing surface."""

    def fill_rect(self, x: float, y: float, width: float, height: float, fill: str) -> None:
        """Fill a rectangle with an outline."""

    def draw_text(self, x: float, y: float, text: str, fill: str) -> None:
        """Draw text centered on a point."""


@dataclass(frozen=True, slots=True)
class NetGeometry:
    """Where the net goes and how big its cells are.

    Attributes:
        cell: Side of one sticker, in pixels.
        gap: Extra space between two faces, in pixels.
        margin: Space around the whole net, in pixels.
    """

    cell: float = 36.0
    gap: float = 4.0
    margin: float = 12.0

    @property
    def width(self) -> float:
        """Return the width of the whole drawing."""
        return 2 * self.margin + NET_COLUMNS * self.cell + 3 * self.gap

    @property
    def height(self) -> float:
        """Return the height of the whole drawing."""
        return 2 * self.margin + NET_ROWS * self.cell + 2 * self.gap

    def cell_origin(self, row: int, column: int) -> tuple[float, float]:
        """Return the top-left corner of a net cell, gaps between faces included."""
        x = self.margin + column * self.cell + (column // FACE_SIZE) * self.gap
        y = self.margin + row * self.cell + (row // FACE_SIZE) * self.gap
        return x, y

    @classmethod
    def fit(cls, width: float, height: float) -> NetGeometry:
        """Return the largest geometry that fits in ``width`` by ``height``."""
        base = cls()
        fixed_x = 2 * base.margin + 3 * base.gap
        fixed_y = 2 * base.margin + 2 * base.gap
        cell = min((width - fixed_x) / NET_COLUMNS, (height - fixed_y) / NET_ROWS)
        return cls(cell=max(cell, 8.0), gap=base.gap, margin=base.margin)


def hex_color(rgb: tuple[int, int, int]) -> str:
    """Return ``#rrggbb`` for an RGB triple."""
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def paint_net(
    painter: Painter,
    cube: Cube,
    geometry: NetGeometry | None = None,
    *,
    palette: dict[Color, tuple[int, int, int]] | None = None,
    show_labels: bool = False,
) -> None:
    """Draw ``cube`` as the traditional cross-shaped net.

    Args:
        painter: The drawing surface.
        cube: The cube to draw.
        geometry: Sizes and placement; defaults to :class:`NetGeometry`.
        palette: Color to RGB mapping; defaults to the standard scheme.
        show_labels: Whether to write the face letter on each center sticker.
    """
    resolved = geometry or NetGeometry()
    colors = DEFAULT_PALETTE if palette is None else palette
    layout = net_layout(cube)
    for row, cells in enumerate(layout.colors):
        for column, color in enumerate(cells):
            if color is None:
                continue
            x, y = resolved.cell_origin(row, column)
            painter.fill_rect(x, y, resolved.cell, resolved.cell, hex_color(colors[color]))
    if show_labels:
        for face in FACE_ORDER:
            row0, column0 = NET_ORIGINS[face]
            x, y = resolved.cell_origin(row0 + 1, column0 + 1)
            half = resolved.cell / 2
            painter.draw_text(x + half, y + half, face.value, LABEL_COLOR)

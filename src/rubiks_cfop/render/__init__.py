"""Rendering of cube states.

The renderer is split in two, so that a GUI can draw the cube its own way:

* :func:`net_layout` turns a state into a structured :class:`NetLayout` -- a grid
  of colors plus the facelet index behind every cell;
* :func:`render_ansi`, :func:`render_emoji` and :func:`render_letters` serialize
  that structure to text, for a terminal.

Nothing in the engine prints: the CLI decides what to do with these strings.
"""

from __future__ import annotations

from rubiks_cfop.render.net import (
    DEFAULT_PALETTE,
    NET_ORIGINS,
    NetLayout,
    net_layout,
    render_ansi,
    render_emoji,
    render_letters,
    render_plain,
)

__all__ = [
    "DEFAULT_PALETTE",
    "NET_ORIGINS",
    "NetLayout",
    "net_layout",
    "render_ansi",
    "render_emoji",
    "render_letters",
    "render_plain",
]

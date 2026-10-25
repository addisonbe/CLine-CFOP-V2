"""A desktop interface for the engine, built with Tkinter from the standard library.

The package is split so that most of it can be tested without a screen:

* :mod:`rubiks_cfop.gui.viewmodel` -- the state and its transitions, no toolkit;
* :mod:`rubiks_cfop.gui.painter` -- the net layout, drawn through a painter
  interface;
* :mod:`rubiks_cfop.gui.app` -- the Tk window, a thin view over the two.

The engine itself never imports this package, so ``import rubiks_cfop`` stays free
of Tkinter.  Start the window with ``rubiks-cfop-gui`` or
``python -m rubiks_cfop.gui``.
"""

from __future__ import annotations

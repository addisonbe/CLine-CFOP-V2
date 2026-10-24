"""Cooperative cancellation for long running searches.

A solve can take a noticeable amount of time, and a GUI must be able to abandon
one (the user closed the window, changed the scramble, or simply gave up).  A
:class:`CancelToken` is a thread-safe flag that a caller sets and a solver polls;
polling is cheap enough to do inside the innermost search loops.
"""

from __future__ import annotations

import threading

__all__ = ["CancelToken"]


class CancelToken:
    """A thread-safe "please stop" flag shared with a running solve.

    The token is deliberately tiny and dependency free: a GUI can create one,
    hand it to a solve that runs on a worker thread, and cancel from the UI
    thread.

    Example:
        >>> token = CancelToken()
        >>> token.cancelled
        False
        >>> token.cancel()
        >>> token.cancelled
        True
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        """Create a fresh, uncancelled token."""
        self._event = threading.Event()

    def cancel(self) -> None:
        """Ask the running solve to stop."""
        self._event.set()

    def reset(self) -> None:
        """Clear the token so it can be reused for another solve."""
        self._event.clear()

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

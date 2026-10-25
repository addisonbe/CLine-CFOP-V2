"""Exception hierarchy for the cube engine.

Every error carries structure that a CLI or GUI can render without parsing a
message: a stable machine-readable :attr:`RubiksError.code`, a human-readable
``message`` and an optional ``details`` mapping (for example the offending token
and its position).  :meth:`RubiksError.to_dict` returns a JSON-serializable view
of all of it.
"""

from __future__ import annotations

__all__ = [
    "CancelledError",
    "InvalidMoveError",
    "InvalidStateError",
    "NotationError",
    "RubiksError",
    "SearchLimitError",
    "SolveTimeoutError",
    "UnsolvableStateError",
]


class RubiksError(Exception):
    """Base class for every error raised by the engine.

    Args:
        message: Human-readable description of the problem.
        **details: Machine-readable context, exposed via :attr:`details`.
    """

    code = "rubiks-error"

    def __init__(self, message: str, **details: object) -> None:
        """Store the message and the structured details of the failure."""
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = dict(details)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable description of this error."""
        return {"code": self.code, "message": self.message, "details": dict(self.details)}

    def __str__(self) -> str:
        """Render the message plus any details, in a stable order."""
        if not self.details:
            return self.message
        rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(self.details.items()))
        return f"{self.message} ({rendered})"


class InvalidMoveError(RubiksError):
    """A single move is not valid WCA notation (for example ``1Rw`` on a 3x3x3)."""

    code = "invalid-move"


class NotationError(RubiksError):
    """A move sequence could not be parsed.

    Attributes:
        token: The offending text exactly as it appeared in the input.
        index: Zero-based position of ``token`` in the token stream.
    """

    code = "notation-error"

    def __init__(self, message: str, *, token: str, index: int, **details: object) -> None:
        """Record the offending token, its position and any extra details."""
        super().__init__(message, token=token, index=index, **details)
        self.token = token
        self.index = index


class InvalidStateError(RubiksError):
    """A cube state is malformed (bad length, wrong sticker counts, moved centers)."""

    code = "invalid-state"


class UnsolvableStateError(RubiksError):
    """A cube state violates the cube's algebraic invariants and cannot be solved."""

    code = "unsolvable-state"


class CancelledError(RubiksError):
    """A solve was canceled cooperatively through its cancellation token."""

    code = "cancelled"


class SolveTimeoutError(RubiksError):
    """A solve exceeded its deadline or its node budget.

    Named with a ``Solve`` prefix so that it does not shadow the builtin
    :exc:`TimeoutError`.
    """

    code = "solve-timeout"


class SearchLimitError(RubiksError):
    """A search exhausted its depth budget without finding a solution.

    This is not a statement about the cube: the state is solvable, the search was
    simply not given enough room.  Raise the depth limits and try again.
    """

    code = "search-limit"

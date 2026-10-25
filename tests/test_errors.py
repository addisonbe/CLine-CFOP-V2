"""Contract tests for the engine exception hierarchy.

These pin the behavior a GUI/CLI relies on: a stable ``code``, a JSON view and
structured details that never require parsing the message.
"""

from __future__ import annotations

import json

import pytest

from rubiks_cfop.errors import (
    CancelledError,
    InvalidMoveError,
    InvalidStateError,
    NotationError,
    RubiksError,
    SolveTimeoutError,
    UnsolvableStateError,
)

SIMPLE_ERRORS: list[type[RubiksError]] = [
    InvalidMoveError,
    InvalidStateError,
    UnsolvableStateError,
    CancelledError,
    SolveTimeoutError,
]
ALL_ERRORS: list[type[RubiksError]] = [*SIMPLE_ERRORS, NotationError]


@pytest.mark.parametrize("error_type", ALL_ERRORS)
def test_every_error_derives_from_base(error_type: type[RubiksError]) -> None:
    assert issubclass(error_type, RubiksError)


def test_error_codes_are_unique_and_kebab_case() -> None:
    codes = [RubiksError.code, *(error_type.code for error_type in ALL_ERRORS)]
    assert len(codes) == len(set(codes))
    for code in codes:
        assert code.replace("-", "").isalnum()
        assert code == code.lower()


@pytest.mark.parametrize("error_type", SIMPLE_ERRORS)
def test_to_dict_is_json_serializable(error_type: type[RubiksError]) -> None:
    error = error_type("boom")
    payload = json.loads(json.dumps(error.to_dict()))
    assert payload == {"code": error_type.code, "message": "boom", "details": {}}


@pytest.mark.parametrize("error_type", SIMPLE_ERRORS)
def test_message_is_preserved(error_type: type[RubiksError]) -> None:
    error = error_type("boom", face="U")
    assert error.message == "boom"
    assert error.details == {"face": "U"}
    assert error.args == ("boom",)


def test_str_without_details_is_the_message() -> None:
    assert str(RubiksError("boom")) == "boom"


def test_str_with_details_is_deterministic() -> None:
    error = RubiksError("boom", b=2, a=1)
    assert str(error) == "boom (a=1, b=2)"
    assert error.details == {"a": 1, "b": 2}


def test_notation_error_exposes_token_and_index() -> None:
    error = NotationError("unknown token", token="Q", index=3)
    assert error.token == "Q"
    assert error.index == 3
    assert error.to_dict() == {
        "code": "notation-error",
        "message": "unknown token",
        "details": {"index": 3, "token": "Q"},
    }
    assert str(error) == "unknown token (index=3, token='Q')"


def test_notation_error_requires_token_and_index() -> None:
    with pytest.raises(TypeError):
        NotationError("missing context")  # type: ignore[call-arg]


def test_solve_timeout_error_does_not_shadow_builtin() -> None:
    assert SolveTimeoutError is not TimeoutError
    assert not issubclass(SolveTimeoutError, TimeoutError)

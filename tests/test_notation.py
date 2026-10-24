"""WCA notation parsing, aliases and error reporting."""

from __future__ import annotations

import pytest

from rubiks_cfop.cube.facelets import SOLVED_FACELETS
from rubiks_cfop.cube.moves import MOVES
from rubiks_cfop.cube.notation import (
    format_moves,
    is_valid_token,
    normalize_sequence,
    parse_moves,
    parse_scramble,
)
from rubiks_cfop.errors import NotationError

SCRAMBLE = "R U R' U' F2 D L2 B' Rw U2 M' x y' z2"


def test_parse_moves_returns_moves() -> None:
    moves = parse_moves("R U R' U'")
    assert [move.name for move in moves] == ["R", "U", "R'", "U'"]
    assert all(move is MOVES[move.name] for move in moves)


def test_parse_moves_accepts_empty_input() -> None:
    assert parse_moves("") == ()
    assert parse_moves("   \n\t ") == ()


def test_parse_moves_ignores_layout() -> None:
    assert parse_moves("R   U\nR'\tU'") == parse_moves("R U R' U'")


def test_parse_scramble_is_parse_moves() -> None:
    assert parse_scramble(SCRAMBLE) == parse_moves(SCRAMBLE)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("R", "R"),
        ("R'", "R'"),
        ("R2", "R2"),
        ("Rw", "Rw"),
        ("RW", "Rw"),
        ("2Rw", "Rw"),
        ("2Rw2", "Rw2"),
        ("r", "Rw"),
        ("r'", "Rw'"),
        ("M", "M"),
        ("m'", "M'"),
        ("E", "E"),
        ("S2", "S2"),
        ("x", "x"),
        ("y'", "y'"),
        ("z2", "z2"),
        ("R2'", "R2"),
        ("R'2", "R2"),
    ],
)
def test_token_aliases(token: str, expected: str) -> None:
    assert parse_moves(token)[0].name == expected
    assert is_valid_token(token)


@pytest.mark.parametrize(
    "token",
    ["1Rw", "3Rw", "2R", "2R2", "Q", "R3", "R'2'", "Rww", "R2w2", "2", "'", "w"],
)
def test_invalid_tokens(token: str) -> None:
    assert not is_valid_token(token)
    with pytest.raises(NotationError) as error:
        parse_moves(token)
    assert error.value.token == token
    assert error.value.index == 0


def test_error_reports_the_offending_token_and_index() -> None:
    with pytest.raises(NotationError) as error:
        parse_moves("R U Q F")
    assert error.value.token == "Q"
    assert error.value.index == 2
    payload = error.value.to_dict()
    assert payload["details"] == {"index": 2, "token": "Q"}


def test_error_message_explains_layer_prefixes() -> None:
    with pytest.raises(NotationError, match="invalid on a 3x3x3"):
        parse_moves("3Rw")
    with pytest.raises(NotationError, match="only valid for wide moves"):
        parse_moves("2R")


def test_format_moves_is_canonical() -> None:
    assert format_moves(parse_moves("r U2 2Rw' R2'")) == "Rw U2 Rw' R2"
    assert format_moves(()) == ""


def test_normalize_sequence_round_trips() -> None:
    normalized = normalize_sequence(SCRAMBLE)
    assert normalized == SCRAMBLE
    assert parse_moves(normalized) == parse_moves(SCRAMBLE)


def test_a_long_scramble_round_trips() -> None:
    text = " ".join(
        f"{base}{suffix}" for base in ("R", "U", "F", "L", "D", "B") for suffix in ("", "2", "'")
    )
    moves = parse_moves(text)
    assert len(moves) == 18
    assert format_moves(moves) == text
    state = SOLVED_FACELETS
    for move in moves:
        state = move.apply_to(state)
    for move in reversed(moves):
        state = move.inverse().apply_to(state)
    assert state == SOLVED_FACELETS

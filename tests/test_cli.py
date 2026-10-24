"""The command line interface: arguments, output shape and exit codes."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from rubiks_cfop.cube.facelets import SOLVED_FACELETS

SCRAMBLE = "R U R' U' F2 D"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the CLI in a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "rubiks_cfop.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def solved_output() -> str:
    """Solve one short scramble once and reuse the output."""
    result = run("--scramble", SCRAMBLE, "--no-color")
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_stage_labels_are_listed(solved_output: str) -> None:
    labels = ("Cross:", "F2L1:", "F2L2:", "F2L3:", "F2L4:")
    for label in labels:
        assert label in solved_output
    assert "OLL (" in solved_output
    assert "PLL (" in solved_output
    assert "Scramble: " + SCRAMBLE in solved_output


def test_net_comes_first(solved_output: str) -> None:
    """The unfolded cube is the first thing printed."""
    first = solved_output.splitlines()[0]
    assert "\u2b1c" in first or any(
        square in first for square in "\U0001f7e5\U0001f7e6\U0001f7e7\U0001f7e8\U0001f7e9"
    )


def test_json_payload() -> None:
    result = run("--scramble", SCRAMBLE, "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["verified"] is True
    assert payload["total_moves"] > 0
    assert len(payload["stages"]) >= 7


def test_colour_output_uses_ansi() -> None:
    result = run("--scramble", SCRAMBLE, "--color")
    assert result.returncode == 0
    assert "\x1b[48;2;" in result.stdout


def test_facelets_input() -> None:
    result = run("--facelets", SOLVED_FACELETS, "--no-color")
    assert result.returncode == 0
    assert "OLL (skip)" in result.stdout


def test_bad_scramble_reports_an_error() -> None:
    result = run("--scramble", "R Q F")
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert result.stdout == ""


def test_cross_colour_option() -> None:
    result = run("--scramble", SCRAMBLE, "--cross", "white", "--no-color")
    assert result.returncode == 0
    assert "Cross colour: white" in result.stdout


def test_cross_options_listing() -> None:
    result = run("--scramble", SCRAMBLE, "--cross-options", "--no-color")
    assert result.returncode == 0
    for color in ("white", "yellow", "green", "blue", "red", "orange"):
        assert color in result.stdout


def test_random_scramble_is_generated() -> None:
    result = run("--random", "--scramble-style", "random-move", "--seed", "5", "--no-color")
    assert result.returncode == 0
    assert "Scramble: " in result.stdout

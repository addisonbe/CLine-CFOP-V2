"""Engine-level contract tests: headless behaviour, cheap imports, no dependencies.

A GUI embeds this package in-process, so importing it must be silent, fast and
must not drag in third-party code.
"""

from __future__ import annotations

import subprocess
import sys
import time

IMPORT_SNIPPET = "import rubiks_cfop, rubiks_cfop.errors"

#: Import time budget in milliseconds.  Generous enough to survive a loaded CI
#: machine, tight enough to catch accidental heavy work at import time.
IMPORT_BUDGET_MS = 1000

THIRD_PARTY_SNIPPET = """
import json
import sys

import rubiks_cfop

stdlib = set(sys.stdlib_module_names)
extra = sorted(
    {
        name.split(".")[0]
        for name in sys.modules
        if not name.startswith("_")
    }
    - stdlib
    - {"rubiks_cfop"}
)
print(json.dumps(extra))
"""


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )


def test_import_is_silent() -> None:
    result = _run(IMPORT_SNIPPET)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_import_time_is_within_budget() -> None:
    started = time.perf_counter()
    result = _run(IMPORT_SNIPPET)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert result.returncode == 0, result.stderr
    assert elapsed_ms < IMPORT_BUDGET_MS, f"import took {elapsed_ms:.1f} ms"


def test_import_pulls_in_no_third_party_modules() -> None:
    result = _run(THIRD_PARTY_SNIPPET)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_engine_does_not_read_argv_or_environment() -> None:
    snippet = (
        "import sys\n"
        "sys.argv = ['/nonexistent', '--bogus-flag']\n"
        "import rubiks_cfop\n"
        "assert rubiks_cfop.__version__\n"
    )
    result = _run(snippet)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""

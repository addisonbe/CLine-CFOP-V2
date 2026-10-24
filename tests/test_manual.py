"""The LaTeX manual: sources present and structurally consistent.

The sandbox has no TeX distribution, so this checks what can be checked without
one: every included file exists, environments and braces balance, only ASCII is
used, and every colour and reference is defined.  `latexmk -pdf main.tex` remains
the real build.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL = REPO_ROOT / "manual"


def test_manual_files_exist() -> None:
    assert (MANUAL / "main.tex").is_file()
    assert (MANUAL / "README.md").is_file()
    sections = sorted((MANUAL / "sections").glob("*.tex"))
    assert len(sections) >= 10
    assert (MANUAL / "appendix" / "gui-plan.tex").is_file()
    assert (MANUAL / "figures" / "net-solved.tex").is_file()


def test_gui_plan_is_in_the_appendix() -> None:
    main = (MANUAL / "main.tex").read_text(encoding="utf-8")
    appendix = main.index("\\appendix")
    assert appendix < main.index("appendix/gui-plan")
    plan = (MANUAL / "appendix" / "gui-plan.tex").read_text(encoding="utf-8")
    for topic in ("Architecture", "Milestones", "Testing", "Threading"):
        assert topic in plan


def test_manual_sources_are_structurally_valid() -> None:
    result = subprocess.run(
        [sys.executable, str(MANUAL / "tools" / "check_manual.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no structural problems found" in result.stdout

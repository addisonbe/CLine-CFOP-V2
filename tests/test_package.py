"""Smoke tests for the package skeleton and its declared public surface."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import rubiks_cfop


def test_python_version_is_at_least_313() -> None:
    assert sys.version_info >= (3, 13)


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", rubiks_cfop.__version__)


def test_every_public_name_is_importable() -> None:
    missing = [name for name in rubiks_cfop.__all__ if not hasattr(rubiks_cfop, name)]
    assert missing == []


def test_all_has_no_duplicates() -> None:
    assert len(rubiks_cfop.__all__) == len(set(rubiks_cfop.__all__))


def test_py_typed_marker_is_shipped() -> None:
    spec = importlib.util.find_spec("rubiks_cfop")
    assert spec is not None
    assert spec.origin is not None
    package_dir = Path(spec.origin).parent
    assert (package_dir / "py.typed").is_file(), "PEP 561 marker missing"


def test_runtime_has_no_third_party_dependencies(repo_root: Path) -> None:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    runtime, _, _ = pyproject.partition("[dependency-groups]")
    assert "dependencies = []" in runtime

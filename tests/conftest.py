"""Shared pytest configuration for the whole suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

REPO_ROOT = Path(__file__).resolve().parent.parent

settings.register_profile(
    "default",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.load_profile("default")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path of the repository root."""
    return REPO_ROOT

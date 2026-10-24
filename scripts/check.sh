#!/usr/bin/env bash
#
# Stage gate: every stage must pass formatting, linting and the full test suite
# before it is committed.  Extra arguments are forwarded to pytest, e.g.
#
#     scripts/check.sh tests/test_cube.py -k moves
#
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== ruff format =="
uv run ruff format --check .

echo "== ruff check =="
uv run ruff check .

echo "== pytest =="
uv run pytest "$@"

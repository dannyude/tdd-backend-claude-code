#!/usr/bin/env bash
# scripts/check.sh  -  the single definition of "done"

# Use the project's virtual environment when it exists (on your machine).
# In CI there is no .venv: packages are installed straight into the runner's Python.
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi

set -euo pipefail

echo "==> ruff lint";      ruff check .
echo "==> ruff format";    ruff format --check .
echo "==> mypy";           mypy app
echo "==> pytest";         pytest -q -x

echo "All checks passed."

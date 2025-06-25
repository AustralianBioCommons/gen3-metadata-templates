#!/usr/bin/env bash
# This script bootstraps a local virtual environment in .venv, installs all
# runtime and dev requirements, installs the project in editable mode, and
# finally builds the distribution archives into the dist/ directory.

set -euo pipefail

# Determine project root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/*}"
cd "$PROJECT_ROOT"

VENV_DIR=".venv"
PYTHON_BIN="python3"

# Create virtual environment if it doesn't exist
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment in $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate the virtual environment
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Upgrade pip to latest
python -m pip install --upgrade pip setuptools wheel

# Install runtime requirements if requirements.txt exists
if [[ -f "requirements.txt" ]]; then
    echo "Installing requirements.txt"
    pip install -r requirements.txt
fi

# Install the 'build' utility to create sdist/wheel
pip install --upgrade build

# Install project (and dev extras) in editable mode
pip install -e .[dev]

# Build the project (source + wheel) under dist/
python -m build

echo "Build complete. Virtual environment located at $VENV_DIR"

#!/usr/bin/env bash

# Resolve the absolute path of the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure the virtual environment is used
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at .venv"
    echo "Please set up the virtual environment first."
    exit 1
fi

# Run the unified CLI with PYTHONPATH set
PYTHONPATH="${PROJECT_ROOT}" exec "$VENV_PYTHON" -m src.cli.main "$@"

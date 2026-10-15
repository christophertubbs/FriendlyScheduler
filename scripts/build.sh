#!/bin/sh
# Invoke in an isolated dev environment with .[dev] installed.
set -eu
FSCHED_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$FSCHED_SOURCE"
python -m build
python -m PyInstaller --clean --noconfirm --onefile --name fsched --paths src scripts/frozen_entry.py
./dist/fsched --version
./dist/fsched submit --help

#!/bin/sh
# Invoke in an isolated dev environment with .[dev] installed.
set -eu
FSCHED_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$FSCHED_SOURCE"
# Fail before producing partial artifacts when freezing cannot work.
python - <<'PYTHON'
"""Validate the build interpreter. TODO(AI-GENERATED): Review build diagnostics."""
from __future__ import annotations

import sys

from PyInstaller.depend.bindepend import get_python_library_path

library: str | None = get_python_library_path()
if library is None:
    raise SystemExit(
        "Frozen builds require a discoverable shared libpython. "
        "Use a shared Python build; manylinux /opt/python interpreters are static."
    )
print(f"Freezing with {sys.executable}; shared library: {library}")
PYTHON
python -m build
python -m PyInstaller --clean --noconfirm --onefile --name fsched --paths src scripts/frozen_entry.py
./dist/fsched --version
./dist/fsched submit --help

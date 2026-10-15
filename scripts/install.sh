#!/bin/sh
# Install from a checkout; dependencies stay in an isolated application venv.
set -eu
FSCHED_SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "${PYTHON:-python3}" "$FSCHED_SOURCE/scripts/install.py" "$@"

"""Thin installed and python -m entry point.

TODO(AI-GENERATED): Review process exit and diagnostic mapping.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from collections.abc import Sequence

from fsched.application import run
from fsched.cli import parse_args
from fsched.models import Arguments


def main(argv: Sequence[str] | None = None) -> int:
    """Parse and dispatch one command, translating expected operational failures.

    :param argv: CLI tokens, or None to read process arguments.
    :return: Application exit code; two denotes invalid input/environment failure.
    TODO(AI-GENERATED): Review error reporting without exposing private argv.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    arguments: Arguments = parse_args(argv)
    try:
        return run(arguments)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"fsched: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

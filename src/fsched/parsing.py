"""Strict unit parsers used by the CLI and submission validation.

TODO(AI-GENERATED): Review boundary validation.
"""

from __future__ import annotations

import argparse
import math
import re


def cpu_value(text: str) -> float:
    """Parse a finite CPU allowance.

    :param text: Positive CPU equivalents, capped at 65536.
    :return: CPU equivalents, permitting fractions down to 0.01.
    :raises argparse.ArgumentTypeError: For malformed or out-of-range values.
    TODO(AI-GENERATED): Review parser limits.
    """
    try:
        value: float = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("CPUs must be a number") from exc
    if not math.isfinite(value) or not 0.01 <= value <= 65536:
        raise argparse.ArgumentTypeError("CPUs must be finite and between 0.01 and 65536")
    return value


def memory_value(text: str) -> int:
    """Parse an integer memory amount with an explicit binary unit.

    :param text: For example 512MiB, 4GiB, or 1000000B; case-insensitive.
    :return: Positive byte count, at most 2**60.
    :raises argparse.ArgumentTypeError: For invalid syntax or range.
    TODO(AI-GENERATED): Review unit grammar.
    """
    match: re.Match[str] | None = re.fullmatch(r"([1-9][0-9]{0,18})(B|KiB|MiB|GiB|TiB)", text, re.I)
    if match is None:
        raise argparse.ArgumentTypeError("use an integer with B, KiB, MiB, GiB or TiB (e.g. 4GiB)")
    powers: dict[str, int] = {"b": 0, "kib": 1, "mib": 2, "gib": 3, "tib": 4}
    value: int = int(match[1]) * 1024 ** powers[match[2].lower()]
    if value > 2**60:
        raise argparse.ArgumentTypeError("memory exceeds 1 EiB")
    return value


def duration_value(text: str) -> int:
    """Parse a positive bounded runtime.

    :param text: Integer followed by s, m, h or d; maximum seven days.
    :return: Runtime in whole seconds.
    :raises argparse.ArgumentTypeError: For invalid syntax or range.
    TODO(AI-GENERATED): Review runtime policy.
    """
    match: re.Match[str] | None = re.fullmatch(r"([1-9][0-9]{0,8})(s|m|h|d)", text)
    if match is None:
        raise argparse.ArgumentTypeError("use a positive duration such as 30s, 20m, 4h or 2d")
    factors: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    value: int = int(match[1]) * factors[match[2]]
    if value > 604800:
        raise argparse.ArgumentTypeError("runtime cannot exceed seven days")
    return value


def job_id_value(text: str) -> str:
    """Validate a generated job identifier before filesystem or unit use.

    :param text: Exactly 32 lowercase hexadecimal characters.
    :return: Unchanged safe identifier.
    :raises ValueError: For any other identifier syntax.
    TODO(AI-GENERATED): Review identifier boundary.
    """
    if re.fullmatch(r"[0-9a-f]{32}", text) is None:
        raise ValueError("job ID must contain exactly 32 lowercase hexadecimal characters")
    return text

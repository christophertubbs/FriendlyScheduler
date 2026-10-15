"""CLI literal argv, duration, memory and CPU validation.

TODO(AI-GENERATED): Review hostile input coverage.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

import pytest

from fsched.cli import parse_args
from fsched.models import Arguments, Submit
from fsched.parsing import cpu_value, duration_value, job_id_value, memory_value


@pytest.mark.parametrize(
    "parser,text",
    [
        (cpu_value, "nan"),
        (cpu_value, "inf"),
        (cpu_value, "0"),
        (cpu_value, "-1"),
        (cpu_value, "0.001"),
        (cpu_value, "65537"),
        (cpu_value, "oops"),
        (memory_value, "1GB"),
        (memory_value, "-1GiB"),
        (memory_value, "0B"),
        (memory_value, "1.5GiB"),
        (memory_value, "9999999999999999999TiB"),
        (duration_value, "0s"),
        (duration_value, "8d"),
        (duration_value, "1.5h"),
        (duration_value, "-1m"),
        (duration_value, "999999999999999999999999s"),
    ],
)
def test_bad_units(parser: Callable[[str], object], text: str) -> None:
    """Malformed and excessive unit values fail with argparse diagnostics.

    :param parser: Boundary parser under test.
    :param text: Invalid external input.
    :return: None; asserts explicit parsing failure.
    TODO(AI-GENERATED): Review parser error coverage.
    """
    with pytest.raises(argparse.ArgumentTypeError):
        parser(text)


@pytest.mark.parametrize("value", ["../secret", "x.service", "a" * 31, "A" * 32, "a" * 33, "a\n"])
def test_bad_identifiers(value: str) -> None:
    """Identifiers cannot escape job or service namespaces.

    :param value: Hostile job ID.
    :return: None; asserts strict rejection.
    TODO(AI-GENERATED): Review identifier validation.
    """
    with pytest.raises(ValueError):
        job_id_value(value)


def test_literal_argv() -> None:
    """Only scheduler options preceding the command are parsed.

    :return: None; asserts tokens and typed dataclass survive intact.
    TODO(AI-GENERATED): Review command boundary semantics.
    """
    tokens: list[str] = ["python", "--help", "x y", "$HOME", "%n", ";rm -rf", "é", "a\nb"]
    parsed: Arguments = parse_args(["submit", "--time-limit", "2h", "--", *tokens])
    assert isinstance(parsed, Submit)
    assert parsed.argv == tuple(tokens)
    assert parsed.duration == 7200
    assert memory_value("512MiB") == 512 * 1024**2
    assert cpu_value(".25") == 0.25


@pytest.mark.parametrize(
    "command",
    [[], ["submit"], ["submit", "--"], ["submit", "--time-limit", "9d", "true"], ["unknown"]],
)
def test_cli_errors(command: list[str]) -> None:
    """Missing commands and invalid scheduler options are rejected.

    :param command: Invalid CLI tokens.
    :return: None; asserts argparse exit status two.
    TODO(AI-GENERATED): Review diagnostic coverage.
    """
    with pytest.raises(SystemExit) as error:
        parse_args(command)
    assert error.value.code == 2


@pytest.mark.parametrize(
    "command", [[], ["submit"], ["list"], ["inspect"], ["cancel"], ["logs"], ["doctor"], ["daemon"]]
)
def test_help(command: list[str]) -> None:
    """Every command provides help without requiring a user bus.

    :param command: Command path receiving --help.
    :return: None; asserts successful help exit.
    TODO(AI-GENERATED): Review public help coverage.
    """
    with pytest.raises(SystemExit) as error:
        parse_args([*command, "--help"])
    assert error.value.code == 0

"""Argparse grammar converted immediately to typed command dataclasses.

TODO(AI-GENERATED): Review help usability and compatibility.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from fsched import __version__
from fsched.models import (
    Arguments,
    Cancel,
    Daemon,
    Doctor,
    Execute,
    Inspect,
    ListJobs,
    Logs,
    Submit,
)
from fsched.parsing import cpu_value, duration_value, memory_value


def parse_args(argv: Sequence[str] | None = None) -> Arguments:
    """Parse CLI options while preserving command arguments literally.

    :param argv: Tokens without program name; None reads process arguments.
    :return: A command-specific immutable dataclass, never Namespace.
    :raises SystemExit: For help, version or invalid CLI syntax.
    TODO(AI-GENERATED): Review examples and argument boundary cases.
    """
    tokens: list[str] = list(sys.argv[1:] if argv is None else argv)
    if tokens[:1] == ["_exec"]:
        internal: argparse.ArgumentParser = argparse.ArgumentParser(prog="fsched _exec")
        internal.add_argument("job_id")
        internal_args: argparse.Namespace = internal.parse_args(tokens[1:])
        return Execute(job_id=internal_args.job_id)
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="fsched",
        description="Conservative, persistent systemd jobs for a shared Linux host.",
        epilog="Start with fsched doctor. No shell expansion is performed by fsched.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="action",
        required=True,
    )
    submit: argparse.ArgumentParser = commands.add_parser(
        "submit",
        help="queue literal command arguments",
        description="Durably queue a command. Limits are automatic unless specified. "
        "Options must precede the command. Acceptance does not mean execution succeeded.",
        epilog="Examples: fsched submit --time-limit 2h python analysis.py --input data.csv; "
        "fsched submit --cpus 0.5 --memory 512MiB -- /usr/bin/sleep 30",
    )
    submit.add_argument("--cpus", type=cpu_value, help="CPU equivalents; default at most 2")
    submit.add_argument("--memory", type=memory_value, help="hard limit, e.g. 512MiB or 4GiB")
    submit.add_argument(
        "--time-limit",
        type=duration_value,
        default=86400,
        help="wall runtime: 30s, 20m, 4h, 2d; default 1d, maximum 7d",
    )
    submit.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="executable followed by literal arguments (explicit sh -c for pipelines)",
    )
    listing: argparse.ArgumentParser = commands.add_parser(
        "list",
        help="show queue and running reservations",
        epilog="Example: fsched list --all --json",
    )
    listing.add_argument("--all", action="store_true", help="include terminal job history")
    listing.add_argument("--json", action="store_true", help="emit a JSON array")
    inspect: argparse.ArgumentParser = commands.add_parser(
        "inspect",
        help="show allocation, command, lifecycle and exit result",
        epilog="Example: fsched inspect 0123456789abcdef0123456789abcdef --json",
    )
    inspect.add_argument("job_id", help="32-character ID printed by submit")
    inspect.add_argument("--json", action="store_true", help="emit a JSON object")
    cancel: argparse.ArgumentParser = commands.add_parser(
        "cancel",
        help="request cancellation of job and all descendants",
        description="Persist cancellation intent. Queued jobs are cancelled immediately; "
        "the worker stops running jobs on its next reconciliation cycle (normally <=5 seconds).",
        epilog="Example: fsched cancel 0123456789abcdef0123456789abcdef",
    )
    cancel.add_argument("job_id", help="existing ID; repeated cancellation is safe")
    logs: argparse.ArgumentParser = commands.add_parser(
        "logs",
        help="read systemd journal output",
        epilog="Example: fsched logs JOB_ID --follow",
    )
    logs.add_argument("job_id", help="existing job ID")
    logs.add_argument(
        "--follow", action="store_true", help="stream new journal entries; Ctrl-C exits"
    )
    doctor: argparse.ArgumentParser = commands.add_parser(
        "doctor",
        help="diagnose manager, linger, cgroups and installation",
        description="Read-only readiness checks. Administrator configuration may be needed "
        "for unified cgroup v2, controller delegation and loginctl enable-linger.",
        epilog="Example: fsched doctor --json",
    )
    doctor.add_argument("--json", action="store_true", help="emit structured readiness results")
    worker: argparse.ArgumentParser = commands.add_parser(
        "daemon",
        help="run queue worker (normally managed by systemd)",
        epilog="Example: fsched daemon --once",
    )
    worker.add_argument("--once", action="store_true", help="perform one cycle and exit")
    namespace: argparse.Namespace = parser.parse_args(tokens)
    if namespace.action == "submit":
        command: list[str] = namespace.command
        if command[:1] == ["--"]:
            command = command[1:]
        if not command:
            submit.error("a command is required")
        return Submit(
            argv=tuple(command),
            cwd=Path.cwd(),
            cpu=namespace.cpus,
            memory=namespace.memory,
            duration=namespace.time_limit,
        )
    if namespace.action == "list":
        return ListJobs(all=namespace.all, json=namespace.json)
    if namespace.action == "inspect":
        return Inspect(job_id=namespace.job_id, json=namespace.json)
    if namespace.action == "cancel":
        return Cancel(job_id=namespace.job_id)
    if namespace.action == "logs":
        return Logs(job_id=namespace.job_id, follow=namespace.follow)
    if namespace.action == "doctor":
        return Doctor(json=namespace.json)
    if namespace.action == "daemon":
        return Daemon(once=namespace.once)
    raise ValueError("unrecognized command")

"""Probe actual delegated enforcement before opting into live integration tests.

Exit 77 denotes unsupported infrastructure, never a passing integration suite.
TODO(AI-GENERATED): Review on disposable RHEL8 and GitHub-hosted runners.
"""

from __future__ import annotations

import argparse
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from fsched.systemd import Systemd, cgroup_directory, verify_limits

LOGGER: logging.Logger = logging.getLogger(__name__)
UNSUPPORTED: int = 77
MEMORY: int = 128 * 1024**2


@dataclass(frozen=True)
class ProbeArguments:
    """Whether unsupported infrastructure should fail instead of reporting a skip.

    TODO(AI-GENERATED): Review explicit strict-validation mode.
    """

    required: bool = False


def probe(manager: Systemd) -> None:
    """Create, verify and remove a uniquely named temporary slice and service.

    Only /usr/bin/sleep runs, with systemd-requested quotas and a 30-second runtime
    ceiling. Inspect both actual cgroups, not root files or a dormant worker.
    No production scheduler units or administrator settings are modified.

    :param manager: User-manager command adapter, injectable for tests.
    :return: None after both kernel cgroups prove enforced CPU/memory/swap/PID limits.
    :raises RuntimeError: For unavailable bus, controller, enforcement or cleanup.
    TODO(AI-GENERATED): Review transient slice creation and cleanup on systemd 239.
    """
    manager.ready()
    name: str = f"fschedprobe{uuid.uuid4().hex}"
    service: str = f"{name}.service"
    slice_unit: str = f"{name}.slice"
    # CPUQuota activates the controller on a real workload. Delegate= alone does
    # not prove any controller was enabled for the worker's app.slice children.
    properties: list[str] = [
        "CPUQuota=10%",
        f"MemoryMax={MEMORY}",
        f"MemoryHigh={MEMORY * 3 // 4}",
        "MemorySwapMax=0",
        "TasksMax=16",
    ]
    completed: bool = False
    try:
        manager.command(
            [
                "systemd-run",
                "--user",
                f"--unit={service}",
                f"--slice={slice_unit}",
                "--service-type=simple",
                "--property=RuntimeMaxSec=30",
                "--property=TimeoutStopSec=2",
                "--property=KillMode=control-group",
                *[f"--property={value}" for value in properties],
                "--",
                "/usr/bin/sleep",
                "30",
            ]
        )
        manager.command(
            [
                "systemctl",
                "--user",
                "set-property",
                "--runtime",
                slice_unit,
                *properties,
            ]
        )
        for unit in (service, slice_unit):
            group: str = manager.command(
                [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    "--property=ControlGroup",
                    "--value",
                ]
            ).strip()
            verify_limits(cgroup_directory(group), cpu=0.1, memory=MEMORY, tasks=16)
        completed = True
    finally:
        # A failed start can still create a unit. Clean up both names, even if
        # verification or one cleanup operation fails. UUIDs avoid user units.
        errors: list[str] = []
        for operation in (["stop", service, slice_unit], ["revert", slice_unit]):
            try:
                manager.command(["systemctl", "--user", *operation])
            except RuntimeError as exc:
                errors.append(str(exc))
        if errors:
            LOGGER.warning("preflight_cleanup_failed details=%s", "; ".join(errors))
            # Preserve an original failure's useful diagnostic. If enforcement
            # succeeded, uncertain cleanup still prevents a supported result.
            if completed:
                raise RuntimeError("temporary preflight unit cleanup failed: " + "; ".join(errors))


def parse_args(argv: Sequence[str] | None = None) -> ProbeArguments:
    """Convert preflight CLI flags into immutable typed configuration.

    :param argv: Argument tokens; None reads the process command line.
    :return: Probe settings, with skipping allowed unless --required is supplied.
    :raises SystemExit: On help or invalid arguments.
    TODO(AI-GENERATED): Review preflight CLI contract.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--required",
        action="store_true",
        help="fail with status 1 rather than skip (77) when unsupported",
    )
    namespace: argparse.Namespace = parser.parse_args(argv)
    return ProbeArguments(required=namespace.required)


def run(arguments: ProbeArguments, manager: Systemd) -> int:
    """Map known runtime limitations to explicit, auditable skip/failure outcomes.

    :param arguments: Whether real integration capability is mandatory.
    :param manager: Injectable user-manager boundary.
    :return: Zero for supported; 77 for unsupported, or one when required.
    TODO(AI-GENERATED): Review unsupported-versus-bug classification.
    """
    try:
        probe(manager)
    except RuntimeError as exc:
        print(f"UNSUPPORTED systemd integration: {exc}")
        return 1 if arguments.required else UNSUPPORTED
    print("SUPPORTED systemd integration: delegated slice and service limits verified")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse and run the infrastructure capability check.

    :param argv: Argument tokens or None for process arguments.
    :return: Supported, explicitly skipped or required-but-unsupported exit status.
    TODO(AI-GENERATED): Review diagnostic output in CI summaries.
    """
    return run(parse_args(argv), Systemd())


if __name__ == "__main__":
    raise SystemExit(main())

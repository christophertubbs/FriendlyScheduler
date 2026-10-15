"""Read-only readiness diagnostics; never claims unmeasured enforcement works.

TODO(AI-GENERATED): Review administrator guidance for each target distribution.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Union

from fsched.models import Budget, Resources
from fsched.paths import Paths
from fsched.policy import budget_for
from fsched.probes import effective_resources, sharing_count
from fsched.systemd import Systemd

Diagnostic = dict[str, Union[str, bool, int, float]]


def diagnose(manager: Systemd, locations: Paths) -> list[Diagnostic]:
    """Probe independent prerequisites and report actionable failures.

    :param manager: User-manager adapter.
    :param locations: Resolved XDG paths for installation checks.
    :return: Named diagnostics with ok flags, detail and optional numeric budgets.
    TODO(AI-GENERATED): Review missing-controller handling.
    """
    checks: list[Diagnostic] = []
    try:
        manager.ready()
        checks.append({"check": "user_manager", "ok": True, "detail": "user bus reachable"})
    except RuntimeError as exc:
        checks.append({"check": "user_manager", "ok": False, "detail": str(exc)})
    try:
        resources: Resources = effective_resources(sharing_count())
        budget: Budget = budget_for(resources)
        checks.append(
            {
                "check": "capacity",
                "ok": True,
                "detail": str(asdict(resources)),
                "cpu_budget": budget.cpu,
                "memory_budget": budget.memory,
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        checks.append({"check": "capacity", "ok": False, "detail": str(exc)})
    try:
        linger: str = manager.command(
            [
                "loginctl",
                "show-user",
                str(os.getuid()),
                "--property=Linger",
                "--value",
            ]
        ).strip()
        checks.append(
            {
                "check": "logout_survival",
                "ok": linger == "yes",
                "detail": "linger enabled"
                if linger == "yes"
                else "administrator: loginctl enable-linger USER",
            }
        )
    except RuntimeError as exc:
        checks.append({"check": "logout_survival", "ok": False, "detail": str(exc)})
    for unit in ("fsched.service", "fsched.slice"):
        checks.append(
            {
                "check": unit,
                "ok": (locations.units / unit).is_file(),
                "detail": str(locations.units / unit),
            }
        )
    try:
        active: str = manager.command(
            ["systemctl", "--user", "is-active", "fsched.service"]
        ).strip()
        checks.append({"check": "worker", "ok": active == "active", "detail": active})
        group: str = manager.command(
            [
                "systemctl",
                "--user",
                "show",
                "fsched.slice",
                "--property=ControlGroup",
                "--value",
            ]
        ).strip()
        root: Path = Path("/sys/fs/cgroup") / group.lstrip("/")
        limits: dict[str, str] = {
            name: (root / name).read_text().strip()
            for name in ("cpu.max", "memory.max", "memory.swap.max", "pids.max")
        }
        enforced: bool = bool(group) and all("max" not in value for value in limits.values())
        checks.append({"check": "slice_enforcement", "ok": enforced, "detail": str(limits)})
    except (RuntimeError, OSError) as exc:
        checks.append({"check": "slice_enforcement", "ok": False, "detail": str(exc)})
    checks.append(
        {
            "check": "login_history",
            "ok": True,
            "detail": (
                "last available; unavailable records still use fallback"
                if shutil.which("last")
                else "last missing; using one-other-user fallback"
            ),
        }
    )
    return checks

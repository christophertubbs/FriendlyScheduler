"""Read bounded login history and effective Linux/cgroup capacity.

TODO(AI-GENERATED): Review probes on RHEL8 unified cgroup hosts.
"""

from __future__ import annotations

import logging
import os
import pwd
import subprocess
from pathlib import Path

from fsched.models import Resources

LOGGER: logging.Logger = logging.getLogger(__name__)


def recent_users(text: str, caller: str) -> int:
    """Count unique eligible usernames in last output.

    :param text: C-locale `last -w -R` records, excluding headers/trailers.
    :param caller: Calling account to exclude along with .adm/.svc accounts.
    :return: Number of distinct other accounts.
    :raises ValueError: For unrecognized records or a truncated history sample.
    TODO(AI-GENERATED): Review history parsing against util-linux variants.
    """
    users: set[str] = set()
    lines: list[str] = text.splitlines()
    records: int = 0
    for line in lines:
        fields: list[str] = line.split()
        if not fields or fields[0] in {"reboot", "shutdown", "wtmp", "btmp", "runlevel"}:
            continue
        if len(fields) < 4:
            raise ValueError("unrecognized last record")
        records += 1
        user: str = fields[0]
        if user != caller and not user.endswith((".adm", ".svc")):
            users.add(user)
    if records >= 10000:
        raise ValueError("login sample reached record limit")
    return len(users)


def sharing_count() -> int:
    """Query recent history, using one other user when history is unavailable.

    :return: Distinct other users; unknown history logs a fallback warning.
    TODO(AI-GENERATED): Review fallback conservatism and warning frequency.
    """
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["last", "--since", "-14days", "-w", "-R", "-n", "10000"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            env={**os.environ, "LC_ALL": "C"},
        )
        if not result.stdout.strip() or len(result.stdout) > 4 * 1024**2:
            raise ValueError("empty or oversized login history")
        return recent_users(result.stdout, pwd.getpwuid(os.getuid()).pw_name)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        LOGGER.warning("login_history_unknown fallback_other_users=1 reason=%s", exc)
        return 1


def effective_resources(
    others: int,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    proc_root: Path = Path("/proc"),
) -> Resources:
    """Measure host capacity constrained by every visible cgroup ancestor.

    :param others: Nonnegative other-user estimate from history.
    :param cgroup_root: Unified cgroup mount, injectable for tests.
    :param proc_root: Proc filesystem root, injectable for tests.
    :return: Effective CPU equivalents, memory capacity/headroom bytes, sharing.
    :raises OSError: If critical kernel measurements are unavailable.
    :raises ValueError: If measurements or cgroup paths cannot be trusted.
    TODO(AI-GENERATED): Verify cgroup namespace visibility on supported hosts.
    """
    fields: dict[str, int] = {}
    for line in (proc_root / "meminfo").read_text().splitlines():
        pieces: list[str] = line.split()
        if pieces and pieces[0] in {"MemTotal:", "MemAvailable:"}:
            fields[pieces[0][:-1]] = int(pieces[1]) * 1024
    if not {"MemTotal", "MemAvailable"} <= fields.keys():
        raise ValueError("required host memory measurements are missing")
    memory: int = fields["MemTotal"]
    available: int = fields["MemAvailable"]
    cpu: float = float(len(os.sched_getaffinity(0)))
    records: list[str] = (proc_root / "self/cgroup").read_text().splitlines()
    unified: list[str] = [line[3:] for line in records if line.startswith("0::")]
    if len(unified) != 1:
        raise ValueError("unified cgroup v2 is required")
    relative: Path = Path(unified[0].lstrip("/"))
    if ".." in relative.parts:
        raise ValueError("cgroup namespace hides ancestry; cannot establish safe capacity")
    current: Path = cgroup_root / relative
    if not current.is_dir():
        raise ValueError("current cgroup is not visible in the cgroup v2 mount")
    while True:
        for filename in ("memory.max", "cpu.max"):
            path: Path = current / filename
            if not path.exists():
                if current != cgroup_root:
                    raise ValueError(f"required controller file missing: {path}")
                continue
            values: list[str] = path.read_text().split()
            if filename == "memory.max" and values[0] != "max":
                ceiling: int = int(values[0])
                usage: int = int((current / "memory.current").read_text())
                memory = min(memory, ceiling)
                available = min(available, max(0, ceiling - usage))
            if filename == "cpu.max" and values[0] != "max":
                cpu = min(cpu, int(values[0]) / int(values[1]))
        if current == cgroup_root:
            break
        current = current.parent
    return Resources(cpu=cpu, memory=memory, available=available, others=others)

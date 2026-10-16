"""Bounded systemd user-manager commands and cgroup enforcement checks.

TODO(AI-GENERATED): Review all properties against RHEL8 systemd 239.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from fsched.models import Budget
from fsched.parsing import job_id_value


class Systemd:
    """Adapter for one account's systemd manager; never invokes a shell.

    TODO(AI-GENERATED): Review platform failure reporting.
    """

    def command(self, argv: list[str]) -> str:
        """Run a short manager command and preserve diagnostic failures.

        :param argv: Literal executable and arguments without shell expansion.
        :return: Captured stdout on success.
        :raises RuntimeError: On timeout, executable failure or nonzero exit.
        TODO(AI-GENERATED): Review subprocess boundaries.
        """
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            if (
                isinstance(exc, subprocess.CalledProcessError)
                and argv[:3] == ["systemctl", "--user", "show"]
                and "LoadState=not-found" in (exc.stdout or "").splitlines()
            ):
                return str(exc.stdout)
            detail: str = str(exc)
            if isinstance(exc, subprocess.CalledProcessError):
                detail = exc.stderr.strip() or detail
            raise RuntimeError(f"systemd operation failed: {detail}") from exc
        return result.stdout

    def ready(self) -> None:
        """Require a live systemd user manager.

        :return: None; performs a bounded read-only bus query.
        :raises RuntimeError: When the manager is inaccessible.
        TODO(AI-GENERATED): Review logout survival separately.
        """
        self.command(["systemctl", "--user", "show", "--property=Version"])

    def configure(self, budget: Budget) -> None:
        """Apply aggregate limits and verify the actual kernel controller files.

        :param budget: CPU equivalents and memory bytes for the job slice.
        :return: None; starts/configures fsched.slice and checks enforcement.
        :raises RuntimeError: If any required controller or limit is unavailable.
        TODO(AI-GENERATED): Review ancestor delegation and limit transitions.
        """
        self.command(["systemctl", "--user", "start", "fsched.slice"])
        self.command(
            [
                "systemctl",
                "--user",
                "set-property",
                "--runtime",
                "fsched.slice",
                f"CPUQuota={budget.cpu * 100:.2f}%",
                "CPUWeight=10",
                f"MemoryMax={budget.memory}",
                f"MemoryHigh={min(budget.memory * 9 // 10, budget.high or budget.memory)}",
                "MemorySwapMax=0",
                "TasksMax=512",
            ]
        )
        group: str = self.command(
            [
                "systemctl",
                "--user",
                "show",
                "fsched.slice",
                "--property=ControlGroup",
                "--value",
            ]
        ).strip()
        root: Path = cgroup_directory(group)
        verify_limits(root, budget.cpu, budget.memory, 512)

    def start(self, identifier: str, cpu: float, memory: int, duration: int) -> None:
        """Start one fixed runner with hard per-job and aggregate protections.

        :param identifier: Generated job ID, not a user-controlled unit name.
        :param cpu: Reserved CPU equivalents.
        :param memory: Memory ceiling bytes.
        :param duration: Maximum wall runtime seconds.
        :return: None; submits a transient service to the user manager.
        TODO(AI-GENERATED): Review timeout, environment and termination behavior.
        """
        unit: str = unit_name(identifier)
        executable: str = runner_executable()
        state_base: str = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
        if any(character in state_base for character in "%$\n\r"):
            raise RuntimeError("XDG_STATE_HOME cannot contain %, $, or line breaks")
        self.command(
            [
                "systemd-run",
                "--user",
                f"--unit={unit}",
                "--slice=fsched.slice",
                "--service-type=simple",
                "--property=RemainAfterExit=yes",
                f"--property=CPUQuota={cpu * 100:.2f}%",
                "--property=CPUWeight=10",
                f"--property=MemoryMax={memory}",
                f"--property=MemoryHigh={memory * 9 // 10}",
                "--property=MemorySwapMax=0",
                "--property=TasksMax=128",
                "--property=Nice=10",
                "--property=OOMScoreAdjust=500",
                "--property=KillMode=control-group",
                "--property=TimeoutStopSec=10",
                "--property=SendSIGKILL=yes",
                f"--property=RuntimeMaxSec={duration}",
                "--property=StandardOutput=journal",
                "--property=StandardError=journal",
                "--property=UMask=0077",
                "--property=NoNewPrivileges=yes",
                # Propagate only path configuration, never the submitting environment.
                f"--setenv=XDG_STATE_HOME={state_base}",
                "--",
                executable,
                "_exec",
                identifier,
            ]
        )

    def status(self, identifier: str) -> dict[str, str]:
        """Read lifecycle properties, including a distinct missing-unit state.

        :param identifier: Generated job ID.
        :return: systemd property mapping; LoadState=not-found is not success.
        TODO(AI-GENERATED): Review transient-unit retention.
        """
        output: str = self.command(
            [
                "systemctl",
                "--user",
                "show",
                unit_name(identifier),
                "--property=LoadState,ActiveState,SubState,Result,ExecMainStatus,ExecMainCode",
            ]
        )
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def stop(self, identifier: str) -> None:
        """Stop a job's entire control group, including grandchildren.

        :param identifier: Generated job ID.
        :return: None; waits for systemd's bounded stop/escalation sequence.
        TODO(AI-GENERATED): Review stop timeout behavior.
        """
        self.command(["systemctl", "--user", "stop", unit_name(identifier)])

    def release(self, identifier: str) -> None:
        """Release a terminal unit after its outcome is durably recorded.

        :param identifier: Completed generated job ID.
        :return: None; stops a retained successful unit or resets failure state.
        TODO(AI-GENERATED): Review cleanup on manager restarts.
        """
        self.stop(identifier)
        # A successful transient unit can disappear as soon as stop completes.
        # Only reset retained failure state; missing units already are released.
        status: dict[str, str] = self.status(identifier)
        if status.get("LoadState") != "not-found":
            try:
                self.command(["systemctl", "--user", "reset-failed", unit_name(identifier)])
            except RuntimeError:
                if self.status(identifier).get("LoadState") != "not-found":
                    raise


def unit_name(identifier: str) -> str:
    """Map a validated identifier into a deterministic service name.

    :param identifier: Exactly 32 lowercase hex characters.
    :return: Safe fsched-job-*.service unit name.
    TODO(AI-GENERATED): Review namespace isolation.
    """
    return f"fsched-job-{job_id_value(identifier)}.service"


def runner_executable() -> str:
    """Find the installed CLI for fixed systemd runner invocations.

    :return: Absolute executable path, using the frozen binary when applicable.
    :raises RuntimeError: If no installed CLI exists or its path is unsafe.
    TODO(AI-GENERATED): Review PyInstaller and virtualenv installation paths.
    """
    candidate: str | None = None
    if getattr(sys, "frozen", False):
        candidate = sys.executable
    elif Path(sys.argv[0]).name == "fsched" and Path(sys.argv[0]).is_file():
        candidate = str(Path(sys.argv[0]).absolute())
    else:
        candidate = shutil.which("fsched")
    if candidate is None:
        raise RuntimeError("install fsched before starting its scheduler")
    path: str = str(Path(candidate).absolute())
    if any(character in path for character in ("%", "$", "\n", "\r")):
        raise RuntimeError("installed fsched path cannot contain %, $, or line breaks")
    return path


def cgroup_directory(group: str, mount: Path = Path("/sys/fs/cgroup")) -> Path:
    """Resolve a real unit cgroup without treating an unstarted unit as the root.

    :param group: Absolute ControlGroup property returned by the user manager.
    :param mount: Unified cgroup mount, injectable for fixture-based tests.
    :return: Unit-specific directory below the mount; never the mount itself.
    :raises RuntimeError: If the property is empty, relative, root or traverses upward.
    TODO(AI-GENERATED): Review unit-path trust assumptions.
    """
    relative: Path = Path(group.lstrip("/"))
    if not group.startswith("/") or not relative.parts or ".." in relative.parts:
        raise RuntimeError("unit has no valid assigned control group; it may not be started yet")
    return mount / relative


def verify_limits(root: Path, cpu: float, memory: int, tasks: int) -> None:
    """Require finite kernel limits no looser than the promised allocation.

    :param root: Actual cgroup directory under the unified mount.
    :param cpu: Maximum CPU equivalents.
    :param memory: Maximum memory bytes.
    :param tasks: Maximum processes/threads.
    :return: None; reads CPU/memory/soft-memory/swap/PID controller files.
    :raises RuntimeError: If enforcement is absent, malformed or too permissive.
    TODO(AI-GENERATED): Review kernel rounding and delegation behavior.
    """
    try:
        measured_memory: str = (root / "memory.max").read_text().strip()
        high: str = (root / "memory.high").read_text().strip()
        swap: str = (root / "memory.swap.max").read_text().strip()
        measured_tasks: str = (root / "pids.max").read_text().strip()
        measured_cpu: list[str] = (root / "cpu.max").read_text().split()
        if (
            not 0 < int(measured_memory) <= memory
            or not 0 < int(high) <= memory
            or swap != "0"
            or not 0 < int(measured_tasks) <= tasks
            or int(measured_cpu[1]) <= 0
            or not 0 < int(measured_cpu[0]) / int(measured_cpu[1]) <= cpu + 0.001
        ):
            raise ValueError("kernel limits do not match requested ceilings")
    except (OSError, ValueError, IndexError) as exc:
        raise RuntimeError(
            f"unsupported runtime: required CPU/memory/swap/PID limits are not enforced "
            f"in {root}: {exc}; ask your administrator "
            "to enable unified cgroup v2 and delegate cpu, memory and pids to your user"
        ) from exc


def execution_group(identifier: str, cpu: float, memory: int) -> None:
    """Prevent the internal runner from accidentally executing outside its capped unit.

    :param identifier: Generated job identifier.
    :param cpu: Job CPU ceiling in equivalents.
    :param memory: Job memory ceiling bytes.
    :return: None; checks own cgroup membership and per-job kernel limits.
    :raises RuntimeError: If the runner is outside the expected constrained service.
    TODO(AI-GENERATED): Review cgroup namespace and path assumptions.
    """
    records: list[str] = Path("/proc/self/cgroup").read_text().splitlines()
    groups: list[str] = [line[3:] for line in records if line.startswith("0::")]
    suffix: str = f"/fsched.slice/{unit_name(identifier)}"
    if len(groups) != 1 or not groups[0].endswith(suffix) or ".." in Path(groups[0]).parts:
        raise RuntimeError("internal runner must execute inside its constrained systemd job unit")
    verify_limits(Path("/sys/fs/cgroup") / groups[0].lstrip("/"), cpu, memory, 128)

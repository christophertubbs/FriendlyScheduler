"""Opt-in actual systemd/cgroup tests; never run unconfined workloads.

TODO(AI-GENERATED): Review on a disposable RHEL8 VM before production deployment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark: list[pytest.MarkDecorator] = [
    pytest.mark.systemd,
    pytest.mark.skipif(
        os.environ.get("FSCHED_SYSTEMD_TESTS") != "1",
        reason="requires explicit opt-in and installed systemd user worker",
    ),
]


def cli(*tokens: str) -> str:
    """Invoke the installed CLI on the real user manager.

    :param tokens: Literal fsched command tokens.
    :return: Successful stdout, with nonzero exits failing the test.
    TODO(AI-GENERATED): Review integration command isolation.
    """
    result: subprocess.CompletedProcess[str] = subprocess.run(
        ["fsched", *tokens],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def wait_state(identifier: str, expected: set[str]) -> dict[str, object]:
    """Wait a bounded interval for an expected durable lifecycle state.

    :param identifier: Existing job ID.
    :param expected: Accepted states; no other terminal outcome is accepted.
    :return: Matching public inspect object.
    TODO(AI-GENERATED): Review bounded timing tolerances.
    """
    deadline: float = time.monotonic() + 60
    while time.monotonic() < deadline:
        job: dict[str, object] = json.loads(cli("inspect", identifier, "--json"))
        if job["state"] in expected:
            return job
        if job["state"] in {"failed", "succeeded", "timed_out", "cancelled"}:
            pytest.fail(f"unexpected terminal outcome: {job}")
        time.sleep(0.5)
    pytest.fail(f"job {identifier} did not reach {expected}")


def test_live_literal_output(tmp_path: Path) -> None:
    """A real detached service preserves difficult argv exactly.

    :param tmp_path: Private output directory.
    :return: None; asserts execution, durable success and literal output.
    TODO(AI-GENERATED): Review terminal/session independence separately.
    """
    output: Path = tmp_path / "result.json"
    tokens: list[str] = ["$HOME", "%n", "a b", "é", "line\nbreak", ""]
    identifier: str = cli(
        "submit",
        "--cpus",
        "0.1",
        "--memory",
        "128MiB",
        "--time-limit",
        "30s",
        sys.executable,
        "-c",
        "import json,sys;open(sys.argv[1],'w').write(json.dumps(sys.argv[2:]))",
        str(output),
        *tokens,
    )
    wait_state(identifier, {"succeeded"})
    assert json.loads(output.read_text()) == tokens


def test_live_timeout_and_kernel_limits(tmp_path: Path) -> None:
    """A service has real kernel limits and systemd terminates its descendants.

    :param tmp_path: Private PID evidence directory.
    :return: None; asserts controller limits, timeout and descendant disappearance.
    TODO(AI-GENERATED): Review live descendant cleanup and PID reuse assumptions.
    """
    evidence: Path = tmp_path / "pid"
    program: str = (
        "import subprocess,time;from pathlib import Path;"
        "p=subprocess.Popen(['/usr/bin/sleep','120']);"
        f"Path({str(evidence)!r}).write_text(str(p.pid));time.sleep(120)"
    )
    identifier: str = cli(
        "submit",
        "--cpus",
        "0.1",
        "--memory",
        "128MiB",
        "--time-limit",
        "15s",
        sys.executable,
        "-c",
        program,
    )
    try:
        job: dict[str, object] = wait_state(identifier, {"running"})
        deadline: float = time.monotonic() + 10
        while not evidence.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert evidence.exists()
        group: str = subprocess.check_output(
            ["systemctl", "--user", "show", str(job["unit"]), "-p", "ControlGroup", "--value"],
            text=True,
        ).strip()
        root: Path = Path("/sys/fs/cgroup") / group.lstrip("/")
        assert int((root / "memory.max").read_text()) == 128 * 1024**2
        assert (root / "memory.swap.max").read_text().strip() == "0"
        assert int((root / "pids.max").read_text()) == 128
        cpu: list[str] = (root / "cpu.max").read_text().split()
        assert int(cpu[0]) / int(cpu[1]) <= 0.101
        wait_state(identifier, {"timed_out"})
        pid: str = evidence.read_text()
        status: Path = Path("/proc") / pid / "stat"
        assert not status.exists() or status.read_text().split()[2] == "Z"
    finally:
        cli("cancel", identifier)


def test_live_cancel() -> None:
    """A real running job accepts durable cancellation and stops promptly.

    :return: None; asserts cancelled state and idempotent repeated requests.
    TODO(AI-GENERATED): Review multi-process cancellation on target hosts.
    """
    identifier: str = cli(
        "submit",
        "--cpus",
        "0.1",
        "--memory",
        "64MiB",
        "--time-limit",
        "60s",
        "/usr/bin/sleep",
        "120",
    )
    try:
        wait_state(identifier, {"running"})
        cli("cancel", identifier)
        wait_state(identifier, {"cancelled"})
        cli("cancel", identifier)
    finally:
        cli("cancel", identifier)

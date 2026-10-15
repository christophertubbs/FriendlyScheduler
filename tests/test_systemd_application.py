"""Adapter enforcement, application validation and direct-exec boundary tests.

TODO(AI-GENERATED): Review mocks against actual user-manager semantics.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fsched.__main__ import main
from fsched.application import execute_job, run, validated_submission
from fsched.models import GIB, Budget, Cancel, Inspect, ListJobs, Submit
from fsched.store import Store
from fsched.systemd import Systemd, runner_executable, unit_name


def test_adapter_literal_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manager receives a fixed runner, never submitted shell syntax.

    :param monkeypatch: Scoped adapter replacement.
    :return: None; asserts all required hard limits and direct argv transport.
    TODO(AI-GENERATED): Review RHEL8 property availability.
    """
    command: MagicMock = MagicMock(return_value="")
    monkeypatch.setattr(Systemd, "command", command)
    monkeypatch.setattr("fsched.systemd.runner_executable", lambda: "/safe/bin/fsched")
    identifier: str = "a" * 32
    Systemd().start(identifier, 0.25, GIB, 300)
    argv: list[str] = command.call_args.args[0]
    assert argv[-4:] == ["--", "/safe/bin/fsched", "_exec", identifier]
    for property_value in (
        "CPUQuota=25.00%",
        "MemoryMax=1073741824",
        "MemorySwapMax=0",
        "TasksMax=128",
        "KillMode=control-group",
        "RuntimeMaxSec=300",
        "NoNewPrivileges=yes",
        "RemainAfterExit=yes",
    ):
        assert f"--property={property_value}" in argv
    assert "--service-type=simple" in argv
    assert unit_name(identifier) == f"fsched-job-{identifier}.service"


def test_missing_enforcement_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful manager call is insufficient without verified kernel limits.

    :param monkeypatch: Scoped command replacement.
    :return: None; asserts missing cgroup files prevent dispatch.
    TODO(AI-GENERATED): Review enforcement diagnostics.
    """
    monkeypatch.setattr(Systemd, "command", MagicMock(return_value="/nonexistent-fsched-test"))
    with pytest.raises(RuntimeError, match="not enforced"):
        Systemd().configure(Budget(1, GIB, GIB))


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("absent"),
        subprocess.TimeoutExpired("systemctl", 20),
        subprocess.CalledProcessError(1, "systemctl", stderr="denied"),
    ],
)
def test_adapter_errors(monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    """Bus, executable and timeout failures remain actionable errors.

    :param monkeypatch: Scoped subprocess replacement.
    :param failure: Specific expected subprocess failure.
    :return: None; asserts translated diagnostic.
    TODO(AI-GENERATED): Review operational error mapping.
    """
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=failure))
    with pytest.raises(RuntimeError, match="systemd operation failed"):
        Systemd().ready()


def test_runner_uses_own_installed_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A service can find its runner even when ~/bin is absent from manager PATH.

    :param monkeypatch: Scoped argv/PATH changes.
    :param tmp_path: Fake executable root.
    :return: None; asserts stable absolute runner path.
    TODO(AI-GENERATED): Review installed entry point discovery.
    """
    executable: Path = tmp_path / "fsched"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    monkeypatch.setattr("sys.argv", [str(executable), "daemon"])
    monkeypatch.setenv("PATH", "/nonexistent")
    assert runner_executable() == str(executable)


@pytest.mark.parametrize(
    "argv,duration",
    [
        ((), 20),
        (("does-not-exist-fsched",), 20),
        (("echo", "x\0y"), 20),
        (("echo",), 0),
        (("echo",), 604801),
    ],
)
def test_submission_invalid(tmp_path: Path, argv: tuple[str, ...], duration: int) -> None:
    """Programmatic submissions obey the same invariants as CLI input.

    :param tmp_path: Working directory.
    :param argv: Invalid literal command.
    :param duration: Invalid or valid duration seconds.
    :return: None; asserts rejection before persistence.
    TODO(AI-GENERATED): Review library input contract.
    """
    with pytest.raises(ValueError):
        validated_submission(Submit(argv, tmp_path, duration=duration))


def test_direct_execution(
    store: Store, submission: Submit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner execs literal argv with no inherited secrets or implicit shell.

    :param store: Private persisted queue.
    :param submission: Valid working directory.
    :param monkeypatch: Scoped exec and cwd replacement.
    :return: None; asserts argv and environment passed to execve.
    TODO(AI-GENERATED): Review minimal environment semantics.
    """
    argv: tuple[str, ...] = ("/usr/bin/echo", "$SECRET", "%n", "a b", "x\ny")
    identifier: str = store.submit(Submit(argv, submission.cwd), 1, GIB)
    store.claim(identifier)
    execute: MagicMock = MagicMock()
    monkeypatch.setattr(os, "execve", execute)
    monkeypatch.setattr(os, "chdir", MagicMock())
    monkeypatch.setenv("SECRET", "not-forwarded")
    monkeypatch.setattr("fsched.application.execution_group", MagicMock())
    execute_job(store, identifier)
    assert execute.call_args.args[1] == list(argv)
    assert "SECRET" not in execute.call_args.args[2]
    assert execute.call_args.args[2]["FSCHED_JOB_ID"] == identifier


def test_runner_respects_cancellation(
    store: Store, submission: Submit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Already-cancelled intent prevents the fixed runner from executing.

    :param store: Private queue.
    :param submission: Harmless command.
    :param monkeypatch: Scoped exec replacement.
    :return: None; asserts no execution.
    TODO(AI-GENERATED): Review cancellation boundary.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.cancel(identifier)
    execute: MagicMock = MagicMock()
    monkeypatch.setattr(os, "execve", execute)
    execute_job(store, identifier)
    execute.assert_not_called()


def test_history_commands_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Inspect, list and durable queued cancellation work without a bus.

    :param tmp_path: Temporary XDG state base.
    :param monkeypatch: Scoped XDG override.
    :param capsys: Captured intentional CLI output.
    :return: None; asserts public JSON contracts.
    TODO(AI-GENERATED): Review offline operation guarantees.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    client: Store = Store(tmp_path / "fsched")
    identifier: str = client.submit(Submit(("true",), tmp_path), 1, GIB)
    client.close()
    assert run(Inspect(identifier, True)) == 0
    assert json.loads(capsys.readouterr().out)["argv"] == ["true"]
    assert run(ListJobs(json=True)) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1
    assert run(Cancel(identifier)) == 0
    capsys.readouterr()
    assert run(ListJobs(json=True)) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert main(["inspect", "../../no"]) == 2


def test_daemon_single_cycle(
    store: Store, submission: Submit, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual worker path executes a complete bounded cycle and releases its lock.

    :param store: Private queue.
    :param submission: Harmless submission.
    :param tmp_path: Test directory containing state.
    :param monkeypatch: Scoped resource/history replacements.
    :return: None; asserts dispatch and repeatability of lock ownership.
    TODO(AI-GENERATED): Review daemon initialization coverage.
    """
    from fsched.models import Resources
    from fsched.scheduler import daemon
    from tests.conftest import FakeManager

    manager: FakeManager = FakeManager()
    identifier: str = store.submit(submission, 1, GIB)
    monkeypatch.setattr("fsched.scheduler.sharing_count", MagicMock(return_value=1))
    monkeypatch.setattr(
        "fsched.scheduler.effective_resources",
        MagicMock(return_value=Resources(8, 16 * GIB, 15 * GIB, 1)),
    )
    daemon(store, manager, tmp_path / "state", once=True)
    daemon(store, manager, tmp_path / "state", once=True)
    assert manager.started == [identifier]


def test_submit_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Typed submission integrates executable resolution, capacity and persistence.

    :param tmp_path: Temporary XDG base/cwd.
    :param monkeypatch: Scoped environmental adapters.
    :param capsys: Capture intentional job-ID output.
    :return: None; asserts durable command and automatically resolved limits.
    TODO(AI-GENERATED): Review whole-command boundary coverage.
    """
    from fsched.models import Resources

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(Systemd, "ready", MagicMock())
    monkeypatch.setattr(Systemd, "command", MagicMock(return_value="active"))
    monkeypatch.setattr("fsched.application.sharing_count", MagicMock(return_value=1))
    monkeypatch.setattr(
        "fsched.application.effective_resources",
        MagicMock(return_value=Resources(16, 64 * GIB, 50 * GIB, 1)),
    )
    assert run(Submit(("/bin/echo", "$HOME", "a b"), tmp_path)) == 0
    identifier: str = capsys.readouterr().out.strip()
    client: Store = Store(tmp_path / "fsched")
    try:
        assert client.get(identifier)["cpu"] == 2
        assert client.get(identifier)["memory"] == 4 * GIB
        assert json.loads(str(client.get(identifier)["argv"]))[-2:] == ["$HOME", "a b"]
    finally:
        client.close()


def test_doctor_reports_independent_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent manager does not hide other prerequisite diagnostics.

    :param tmp_path: Temporary XDG locations.
    :param monkeypatch: Scoped failing platform adapters.
    :return: None; asserts explicit failing readiness without state mutation.
    TODO(AI-GENERATED): Review unsupported-host behavior.
    """
    from fsched.doctor import Diagnostic, diagnose
    from fsched.models import Resources
    from fsched.paths import Paths

    monkeypatch.setattr(Systemd, "command", MagicMock(side_effect=RuntimeError("no bus")))
    monkeypatch.setattr("fsched.doctor.sharing_count", MagicMock(return_value=1))
    monkeypatch.setattr(
        "fsched.doctor.effective_resources",
        MagicMock(return_value=Resources(8, 16 * GIB, 15 * GIB, 1)),
    )
    checks: list[Diagnostic] = diagnose(Systemd(), Paths(tmp_path / "state", tmp_path / "units"))
    assert any(check["check"] == "capacity" and check["ok"] for check in checks)
    assert any(check["check"] == "user_manager" and not check["ok"] for check in checks)
    assert any(check["check"] == "logout_survival" and not check["ok"] for check in checks)
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    "filename,value",
    [
        ("cpu.max", "max 100000"),
        ("cpu.max", "200000 100000"),
        ("cpu.max", "1000 0"),
        ("memory.max", "max"),
        ("memory.max", "2147483648"),
        ("memory.high", "max"),
        ("memory.swap.max", "1"),
        ("pids.max", "max"),
        ("pids.max", "129"),
        ("memory.max", "0"),
    ],
)
def test_kernel_enforcement_validation(tmp_path: Path, filename: str, value: str) -> None:
    """Malformed or weaker kernel controls cannot be accepted as protective.

    :param tmp_path: Synthetic cgroup directory.
    :param filename: Controller to corrupt.
    :param value: Unsafe controller content.
    :return: None; asserts both valid controls and rejection after corruption.
    TODO(AI-GENERATED): Review kernel-unit fidelity.
    """
    from fsched.systemd import verify_limits

    controls: dict[str, str] = {
        "cpu.max": "100000 100000",
        "memory.max": str(GIB),
        "memory.high": str(GIB * 9 // 10),
        "memory.swap.max": "0",
        "pids.max": "128",
    }
    for name, content in controls.items():
        (tmp_path / name).write_text(content)
    verify_limits(tmp_path, 1, GIB, 128)
    (tmp_path / filename).write_text(value)
    with pytest.raises(RuntimeError, match="not enforced"):
        verify_limits(tmp_path, 1, GIB, 128)


def test_internal_runner_refuses_unconfined_execution(store: Store, submission: Submit) -> None:
    """Calling the private runner directly cannot bypass cgroup protections.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts refusal outside the exact generated service cgroup.
    TODO(AI-GENERATED): Review accidental-bypass prevention.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    with pytest.raises(RuntimeError, match="constrained systemd"):
        execute_job(store, identifier)

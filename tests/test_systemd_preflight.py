"""Infrastructure skip classification and isolated-probe enforcement tests.

TODO(AI-GENERATED): Review alongside real systemd integration evidence.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from fsched.systemd import Systemd


def preflight_module() -> ModuleType:
    """Load the standalone probe without running its command-line entry point.

    :return: The preflight script module with typed configuration and probe functions.
    TODO(AI-GENERATED): Review isolated script loading.
    """
    path: Path = Path(__file__).resolve().parents[1] / "scripts/check_systemd.py"
    spec: ModuleSpec | None = importlib.util.spec_from_file_location("fsched_preflight", path)
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_probe_checks_real_service_and_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live test requires verified kernel controls on both disposable units.

    :param monkeypatch: Scope manager and kernel verification fakes.
    :return: None; asserts both cgroups are verified and unique units cleaned up.
    TODO(AI-GENERATED): Review disposable unit naming and cleanup commands.
    """
    module: ModuleType = preflight_module()
    manager: Systemd = Systemd()
    command: MagicMock = MagicMock(side_effect=["", "", "/test.service", "/test.slice", "", ""])
    checked: MagicMock = MagicMock()
    monkeypatch.setattr(manager, "ready", MagicMock())
    monkeypatch.setattr(manager, "command", command)
    monkeypatch.setattr(module, "verify_limits", checked)
    module.probe(manager)
    assert checked.call_count == 2
    assert checked.call_args_list[0].args[0] == Path("/sys/fs/cgroup/test.service")
    assert checked.call_args_list[1].args[0] == Path("/sys/fs/cgroup/test.slice")
    start: list[str] = command.call_args_list[0].args[0]
    assert start[0] == "systemd-run"
    assert start[-2:] == ["/usr/bin/sleep", "30"]
    assert "--property=CPUQuota=10%" in start
    assert "--property=MemorySwapMax=0" in start
    assert "fsched.slice" not in " ".join(start)
    assert command.call_args_list[-2].args[0][2] == "stop"
    assert command.call_args_list[-1].args[0][2] == "revert"


@pytest.mark.parametrize("required,expected", [(False, 77), (True, 1)])
def test_unsupported_is_explicit(
    required: bool,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing delegation is a visible skip, or a failure for mandatory validation.

    :param required: Whether a real host capability is required.
    :param expected: Distinct expected process exit status.
    :param monkeypatch: Scope the unavailable user bus.
    :param capsys: Captured preflight diagnostic output.
    :return: None; asserts no unsupported result is reported as successful validation.
    TODO(AI-GENERATED): Review explicit skip policy.
    """
    module: ModuleType = preflight_module()
    monkeypatch.setattr(module, "probe", MagicMock(side_effect=RuntimeError("no delegated CPU")))
    assert module.run(module.ProbeArguments(required=required), Systemd()) == expected
    assert "UNSUPPORTED" in capsys.readouterr().out


def test_probe_cleanup_on_kernel_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed kernel-limit check still removes the temporary service and slice.

    :param monkeypatch: Scope a manager success followed by absent controller files.
    :return: None; asserts cleanup occurs and infrastructure remains unsupported.
    TODO(AI-GENERATED): Review cleanup after partial creation.
    """
    module: ModuleType = preflight_module()
    manager: Systemd = Systemd()
    command: MagicMock = MagicMock(side_effect=["", "", "/test.service", "", ""])
    monkeypatch.setattr(manager, "ready", MagicMock())
    monkeypatch.setattr(manager, "command", command)
    monkeypatch.setattr(module, "verify_limits", MagicMock(side_effect=RuntimeError("no cpu.max")))
    with pytest.raises(RuntimeError, match="cpu.max"):
        module.probe(manager)
    assert command.call_args_list[-2].args[0][2] == "stop"
    assert command.call_args_list[-1].args[0][2] == "revert"


def test_unexpected_probe_bug_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected programming error is not converted into an infrastructure skip.

    :param monkeypatch: Inject a representative programming error.
    :return: None; asserts the error remains fatal.
    TODO(AI-GENERATED): Review skip boundary against hidden failures.
    """
    module: ModuleType = preflight_module()
    monkeypatch.setattr(module, "probe", MagicMock(side_effect=TypeError("programming bug")))
    with pytest.raises(TypeError, match="programming bug"):
        module.run(module.ProbeArguments(), Systemd())


def test_cleanup_failure_preserves_original_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Partial creation failures retain the cause even if cleanup also cannot connect.

    :param monkeypatch: Scope initial and cleanup manager errors.
    :return: None; asserts the original unsupported-controller cause remains visible.
    TODO(AI-GENERATED): Review error provenance after partial unit creation.
    """
    module: ModuleType = preflight_module()
    manager: Systemd = Systemd()
    monkeypatch.setattr(manager, "ready", MagicMock())
    command: MagicMock = MagicMock(
        side_effect=[
            RuntimeError("CPU unavailable"),
            RuntimeError("stop denied"),
            RuntimeError("revert denied"),
        ]
    )
    monkeypatch.setattr(manager, "command", command)
    with pytest.raises(RuntimeError, match="CPU unavailable"):
        module.probe(manager)
    assert command.call_count == 3


def test_successful_probe_requires_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verified limits alone do not excuse leaving a disposable probe service running.

    :param monkeypatch: Scope valid controls followed by a failed stop operation.
    :return: None; asserts cleanup uncertainty cannot produce a supported outcome.
    TODO(AI-GENERATED): Review bounded temporary-service lifecycle.
    """
    module: ModuleType = preflight_module()
    manager: Systemd = Systemd()
    monkeypatch.setattr(manager, "ready", MagicMock())
    monkeypatch.setattr(
        manager,
        "command",
        MagicMock(
            side_effect=[
                "",
                "",
                "/test.service",
                "/test.slice",
                RuntimeError("stop denied"),
                "",
            ]
        ),
    )
    monkeypatch.setattr(module, "verify_limits", MagicMock())
    with pytest.raises(RuntimeError, match="cleanup failed"):
        module.probe(manager)

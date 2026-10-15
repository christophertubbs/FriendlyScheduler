"""Installer repeatability and preservation of existing files.

TODO(AI-GENERATED): Review actual source and frozen packaging smoke evidence.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest


def installer_module() -> ModuleType:
    """Load the installer without executing its CLI.

    :return: Standalone installer module.
    TODO(AI-GENERATED): Review test import path stability.
    """
    path: Path = Path(__file__).resolve().parents[1] / "scripts/install.py"
    spec: ModuleSpec | None = importlib.util.spec_from_file_location("fsched_installer", path)
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_installer_repeatable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Frozen installation preserves modified files and repeats unchanged writes.

    :param tmp_path: Temporary user installation root.
    :param monkeypatch: Scoped XDG overrides.
    :return: None; asserts managed-file protection and XDG state propagation.
    TODO(AI-GENERATED): Review real frozen artifact separately.
    """
    module: ModuleType = installer_module()
    for variable, suffix in [
        ("XDG_DATA_HOME", "data"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_STATE_HOME", "state"),
    ]:
        monkeypatch.setenv(variable, str(tmp_path / suffix))
    artifact: Path = tmp_path / "artifact"
    artifact.write_bytes(b"#!/bin/sh\nexit 0\n")
    artifact.chmod(0o755)
    target: Path = tmp_path / "bin"
    module.install(target, artifact, False)
    module.install(target, artifact, False)
    service: Path = tmp_path / "config/systemd/user/fsched.service"
    assert f"XDG_STATE_HOME={tmp_path}/state" in service.read_text()
    service.write_text("user customized\n")
    with pytest.raises(ValueError, match="modified"):
        module.install(target, artifact, False)
    assert service.read_text() == "user customized\n"


def test_unmanaged_bin_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrelated executable cannot be overwritten by installation.

    :param tmp_path: Temporary install root.
    :param monkeypatch: Scoped XDG configuration.
    :return: None; asserts original content survives.
    TODO(AI-GENERATED): Review preservation coverage.
    """
    module: ModuleType = installer_module()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    executable: Path = tmp_path / "bin/fsched"
    executable.parent.mkdir()
    executable.write_text("unrelated")
    with pytest.raises(ValueError, match="unmanaged"):
        module.install(executable.parent, None, False)
    assert executable.read_text() == "unrelated"

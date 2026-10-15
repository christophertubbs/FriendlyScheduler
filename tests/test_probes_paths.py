"""Kernel fixture probes, history exclusions and private-path attacks.

TODO(AI-GENERATED): Review cgroup and login-history compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fsched.models import GIB, Resources
from fsched.paths import paths, private_directory, secure_file
from fsched.probes import effective_resources, recent_users, sharing_count
from fsched.store import Store


def test_login_exclusions() -> None:
    """Count accounts, excluding caller, administrative/service suffixes and markers.

    :return: None; asserts unique eligible users only.
    TODO(AI-GENERATED): Review realistic last record fixtures.
    """
    text: str = "\n".join(
        f"{name} pts/0 Mon Jan 1 00:00 - 01:00"
        for name in ["me", "other", "other", "third", "root.adm", "batch.svc"]
    )
    text += "\nreboot system boot\nwtmp begins Mon Jan 1\n"
    assert recent_users(text, "me") == 2


@pytest.mark.parametrize("text", ["garbage", "bob pts/1", "x pts/0 Mon Jan\n" * 10000])
def test_history_unknown(text: str) -> None:
    """Malformed and capped history cannot silently report an idle host.

    :param text: Untrustworthy login history.
    :return: None; asserts explicit unknown classification.
    TODO(AI-GENERATED): Review fallback semantics.
    """
    with pytest.raises(ValueError):
        recent_users(text, "me")


def test_missing_last_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing utility falls back conservatively without blocking all work.

    :param monkeypatch: Scoped environment replacement.
    :return: None; asserts fallback sharing count.
    TODO(AI-GENERATED): Review fallback visibility.
    """
    monkeypatch.setenv("PATH", "/nonexistent")
    assert sharing_count() == 1


def test_nested_cgroup_capacity(tmp_path: Path) -> None:
    """Tighter ancestors constrain both CPU and memory headroom.

    :param tmp_path: Synthetic proc/cgroup root.
    :return: None; asserts all visible ancestor ceilings are respected.
    TODO(AI-GENERATED): Review kernel fixture fidelity.
    """
    proc: Path = tmp_path / "proc"
    root: Path = tmp_path / "cgroup"
    (proc / "self").mkdir(parents=True)
    (root / "user/job").mkdir(parents=True)
    (proc / "meminfo").write_text(
        f"MemTotal: {16 * GIB // 1024} kB\nMemAvailable: {10 * GIB // 1024} kB\n"
    )
    (proc / "self/cgroup").write_text("0::/user/job\n")
    for group, quota, memory, usage in [
        (root, "max 100000", "max", 0),
        (root / "user", "50000 100000", str(2 * GIB), GIB),
        (root / "user/job", "max 100000", str(8 * GIB), 0),
    ]:
        (group / "cpu.max").write_text(quota)
        (group / "memory.max").write_text(memory)
        (group / "memory.current").write_text(str(usage))
    measured: Resources = effective_resources(1, root, proc)
    assert measured.cpu == 0.5
    assert measured.memory == 2 * GIB
    assert measured.available == GIB
    (proc / "self/cgroup").write_text("0::/../../hidden\n")
    with pytest.raises(ValueError, match="hides ancestry"):
        effective_resources(1, root, proc)


def test_xdg_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """XDG overrides are honored and relative values rejected.

    :param monkeypatch: Scoped environment replacement.
    :param tmp_path: Absolute temporary base.
    :return: None; asserts standard path semantics.
    TODO(AI-GENERATED): Review empty-variable defaults.
    """
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert paths().state == tmp_path / "fsched"
    monkeypatch.setenv("XDG_STATE_HOME", "relative")
    with pytest.raises(ValueError):
        paths()


def test_unsafe_state_paths(tmp_path: Path) -> None:
    """Symlink, hardlink and public state files cannot be adopted.

    :param tmp_path: Private temporary root.
    :return: None; asserts path protections and owner-only fresh modes.
    TODO(AI-GENERATED): Review filesystem race threat model.
    """
    target: Path = tmp_path / "target"
    private_directory(target)
    linked: Path = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        Store(linked)
    target.chmod(0o755)
    with pytest.raises(ValueError):
        Store(target)
    target.chmod(0o700)
    descriptor: int = secure_file(target / "file")
    os.close(descriptor)
    assert (target / "file").stat().st_mode & 0o777 == 0o600
    os.link(target / "file", target / "hardlink")
    with pytest.raises(ValueError):
        secure_file(target / "hardlink")

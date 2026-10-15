"""XDG path resolution and private owner-controlled state directories.

TODO(AI-GENERATED): Review filesystem trust boundaries.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Private state and standard systemd user configuration directories.

    TODO(AI-GENERATED): Review XDG defaults.
    """

    state: Path
    units: Path


def xdg_path(name: str, default: Path) -> Path:
    """Resolve an XDG base, rejecting relative values.

    :param name: Environment variable name.
    :param default: Absolute fallback under the user's home directory.
    :return: Absolute base directory without resolving symlinks.
    :raises ValueError: For a nonempty relative XDG value.
    TODO(AI-GENERATED): Review configuration boundary.
    """
    value: str = os.environ.get(name, "")
    path: Path = Path(value) if value else default
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return path


def paths() -> Paths:
    """Compute configured locations without creating files.

    :return: State and systemd unit directories using XDG base variables.
    TODO(AI-GENERATED): Review installation path consistency.
    """
    home: Path = Path.home()
    return Paths(
        state=xdg_path("XDG_STATE_HOME", home / ".local/state") / "fsched",
        units=xdg_path("XDG_CONFIG_HOME", home / ".config") / "systemd/user",
    )


def private_directory(path: Path) -> None:
    """Create or validate a private state directory without trusting symlinks.

    :param path: Absolute application state directory to create or validate.
    :return: None; creates missing directories with owner-only final permissions.
    :raises ValueError: For symlink ancestors, foreign ownership or unsafe mode.
    TODO(AI-GENERATED): Review same-account race assumptions.
    """
    for ancestor in [*reversed(path.parents), path]:
        if ancestor.is_symlink():
            raise ValueError(f"symlink state path is not allowed: {ancestor}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info: os.stat_result = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError(f"state directory must be owned by you with mode 0700: {path}")


def secure_file(path: Path) -> int:
    """Open an owner-only regular file with symlink protection.

    :param path: File inside a previously validated private directory.
    :return: Read/write descriptor owned by the caller; caller must close it.
    :raises ValueError: For foreign-owned, multiply-linked or non-private files.
    TODO(AI-GENERATED): Review local filesystem adversarial cases.
    """
    descriptor: int = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    info: os.stat_result = os.fstat(descriptor)
    if (
        info.st_uid != os.getuid()
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        os.close(descriptor)
        raise ValueError(f"unsafe private file: {path}")
    return descriptor

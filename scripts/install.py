"""Repeatable per-user source or frozen installation with managed-file checks.

TODO(AI-GENERATED): Review upgrade atomicity and distribution-specific integration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstallArguments:
    """Validated installer command settings.

    bin_dir is the executable directory; binary selects a frozen artifact;
    activate requests only this account's unit activation.
    TODO(AI-GENERATED): Review installer CLI configuration.
    """

    bin_dir: Path
    binary: Path | None
    activate: bool


def base(name: str, default: Path) -> Path:
    """Resolve an absolute XDG installation base.

    :param name: XDG environment variable.
    :param default: Absolute fallback path.
    :return: Configured absolute path.
    :raises ValueError: For relative values or unsafe systemd characters.
    TODO(AI-GENERATED): Review path policy.
    """
    result: Path = Path(os.environ.get(name) or default)
    if not result.is_absolute() or any(char in str(result) for char in "%$\n\r"):
        raise ValueError(f"{name} must be absolute and contain no %, $, or line breaks")
    return result


def digest(path: Path) -> str:
    """Hash an existing regular file without accepting a symlink.

    :param path: Managed file path.
    :return: SHA256 digest, or empty string for a missing path.
    :raises ValueError: For symlinks and nonregular existing paths.
    TODO(AI-GENERATED): Review managed-file upgrade protection.
    """
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"refusing nonregular target: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def write_atomic(path: Path, content: bytes, mode: int) -> None:
    """Replace a preflighted managed file using a same-directory rename.

    :param path: Destination inside an installation directory.
    :param content: Complete replacement bytes.
    :param mode: POSIX permission bits.
    :return: None; creates parent directories and atomically replaces the file.
    TODO(AI-GENERATED): Review crash recovery across multiple managed files.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int
    temporary: str
    descriptor, temporary = tempfile.mkstemp(prefix=".fsched-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(bin_dir: Path, binary: Path | None, activate: bool) -> None:
    """Install application and units without modifying administrator settings.

    :param bin_dir: Explicit absolute executable directory, normally ~/bin.
    :param binary: Existing frozen executable, or None for a source venv install.
    :param activate: Reload/enable/start only this account's worker when true.
    :return: None; writes managed artifacts and prints next steps.
    :raises ValueError: For unsafe paths or modified/unmanaged destinations.
    TODO(AI-GENERATED): Review interrupted upgrade recovery.
    """
    home: Path = Path.home()
    data: Path = base("XDG_DATA_HOME", home / ".local/share") / "fsched"
    config: Path = base("XDG_CONFIG_HOME", home / ".config") / "systemd/user"
    state: Path = base("XDG_STATE_HOME", home / ".local/state")
    if not bin_dir.is_absolute() or any(char in str(bin_dir) for char in "%$\n\r"):
        raise ValueError("bin directory must be absolute and contain no %, $, or line breaks")
    for target in (data, config, state, bin_dir):
        for ancestor in [target, *target.parents]:
            if ancestor.is_symlink():
                raise ValueError(f"symlink installation path: {ancestor}")
    executable: Path = bin_dir / "fsched"
    service: Path = config / "fsched.service"
    slice_file: Path = config / "fsched.slice"
    manifest: Path = data / "install.json"
    previous: dict[str, str] = json.loads(manifest.read_text()) if manifest.exists() else {}
    for path in (executable, service, slice_file):
        existing: str = digest(path)
        if existing and existing != previous.get(str(path)):
            raise ValueError(f"refusing to overwrite unmanaged or modified file: {path}")
    if binary is not None:
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("--binary must be an executable PyInstaller artifact")
        write_atomic(executable, binary.read_bytes(), 0o755)
    else:
        environment: Path = data / "venv"
        source: Path = Path(__file__).resolve().parents[1]
        if " " in str(environment) or len(str(environment / "bin/python")) > 120:
            raise ValueError("source venv path must be short and contain no spaces (shebang limit)")
        if not (environment / "bin/python").exists():
            venv.EnvBuilder(with_pip=True).create(environment)
        subprocess.run(
            [str(environment / "bin/python"), "-m", "pip", "install", str(source)], check=True
        )
        # A small generated executable uses the dedicated venv interpreter; argv
        # is passed through literally. No activation or PATH change is required.
        wrapper: str = (
            f"#!{environment}/bin/python\n"
            '"""Installed CLI. TODO(AI-GENERATED): Review generated wrapper."""\n'
            "from fsched.__main__ import main\nraise SystemExit(main())\n"
        )
        write_atomic(executable, wrapper.encode(), 0o755)
    quoted: str = str(executable).replace("\\", "\\\\").replace('"', '\\"')
    quoted_state: str = str(state).replace("\\", "\\\\").replace('"', '\\"')
    service_text: str = f'''# Managed by fsched installer; hashes protect local edits.
[Unit]
Description=FriendlyScheduler queue worker
After=default.target

[Service]
Type=simple
ExecStart="{quoted}" daemon
Environment="XDG_STATE_HOME={quoted_state}"
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
'''
    slice_text: str = """# Managed by fsched installer; runtime limits set before dispatch.
[Unit]
Description=FriendlyScheduler constrained jobs

[Slice]
CPUAccounting=yes
MemoryAccounting=yes
TasksAccounting=yes
"""
    write_atomic(service, service_text.encode(), 0o644)
    write_atomic(slice_file, slice_text.encode(), 0o644)
    recorded: dict[str, str] = {
        str(path): digest(path) for path in (executable, service, slice_file)
    }
    write_atomic(manifest, json.dumps(recorded, indent=2).encode(), 0o600)
    if activate:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "fsched.service"], check=True)
        subprocess.run(["systemctl", "--user", "restart", "fsched.service"], check=True)
    print(f"Installed {executable}. Add {bin_dir} to PATH, then run fsched doctor.")
    if not activate:
        print(
            "Start: systemctl --user daemon-reload && systemctl --user enable --now fsched.service"
        )
    print("For logout survival ask your administrator to enable linger for your account.")


def main() -> int:
    """Parse installation options and report expected failures.

    :return: Zero on success, two on invalid input or failed installation.
    TODO(AI-GENERATED): Review CLI error mapping.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bin-dir",
        type=Path,
        default=Path.home() / "bin",
        help="executable directory; default ~/bin; alternatively ~/.local/bin",
    )
    parser.add_argument("--binary", type=Path, help="install a frozen artifact instead of source")
    parser.add_argument("--no-start", action="store_true", help="write units without starting them")
    namespace: argparse.Namespace = parser.parse_args()
    arguments: InstallArguments = InstallArguments(
        bin_dir=namespace.bin_dir,
        binary=namespace.binary,
        activate=not namespace.no_start,
    )
    try:
        install(arguments.bin_dir, arguments.binary, arguments.activate)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"install: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

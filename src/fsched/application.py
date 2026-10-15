"""Application dispatch, submission validation and fixed direct-exec runner.

TODO(AI-GENERATED): Review execution and state trust boundaries.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from fsched.doctor import Diagnostic, diagnose
from fsched.models import (
    Arguments,
    Cancel,
    Daemon,
    Doctor,
    Execute,
    Inspect,
    ListJobs,
    Logs,
    Resources,
    Submit,
)
from fsched.paths import Paths, paths
from fsched.policy import allocation, budget_for
from fsched.probes import effective_resources, sharing_count
from fsched.scheduler import daemon
from fsched.store import Job, Store
from fsched.systemd import Systemd, execution_group, unit_name


def validated_submission(request: Submit) -> Submit:
    """Resolve executable and validate programmatic as well as CLI submission.

    :param request: Literal argv, cwd and optional resource overrides.
    :return: Copy with absolute executable and working directory.
    :raises ValueError: For missing executable, invalid cwd/argv or runtime.
    TODO(AI-GENERATED): Review executable resolution semantics.
    """
    if not request.argv or any("\0" in argument for argument in request.argv):
        raise ValueError("a nonempty command without NUL characters is required")
    if not request.cwd.is_absolute() or not request.cwd.is_dir():
        raise ValueError("working directory must be an existing absolute directory")
    if not 1 <= request.duration <= 604800:
        raise ValueError("runtime must be between one second and seven days")
    executable: str | None
    if "/" in request.argv[0]:
        candidate: Path = request.cwd / request.argv[0]
        executable = (
            str(candidate.absolute())
            if candidate.is_file() and os.access(candidate, os.X_OK)
            else None
        )
    else:
        executable = shutil.which(request.argv[0])
    if executable is None:
        raise ValueError(f"executable not found or not executable: {request.argv[0]}")
    return replace(request, argv=(str(Path(executable).absolute()), *request.argv[1:]))


def execute_job(store: Store, identifier: str) -> None:
    """Replace the fixed runner with literal job argv and a minimal environment.

    :param store: Private queue containing the starting/running job.
    :param identifier: Valid generated job identifier.
    :return: Never on success; None when cancellation prevents execution.
    :raises ValueError: If the job is not in an executable lifecycle state.
    TODO(AI-GENERATED): Review minimal environment and cancellation window.
    """
    job: Job = store.get(identifier)
    if job["cancel_requested"]:
        return
    if job["state"] not in {"starting", "running"}:
        raise ValueError("runner may only execute a starting or running job")
    execution_group(identifier, float(str(job["cpu"])), int(str(job["memory"])))
    argv: list[str] = json.loads(str(job["argv"]))
    directory: str = str(job["cwd"])
    environment: dict[str, str] = {
        "HOME": str(Path.home()),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "FSCHED_JOB_ID": identifier,
    }
    store.close()
    os.chdir(directory)
    os.execve(argv[0], argv, environment)


def run(arguments: Arguments) -> int:
    """Execute one typed application command without reading sys.argv.

    :param arguments: Validated command-specific dataclass.
    :return: Zero on success, one for failed readiness; raises operational errors.
    TODO(AI-GENERATED): Review stdout contracts and resource validation.
    """
    locations: Paths = paths()
    manager: Systemd = Systemd()
    if isinstance(arguments, Doctor):
        checks: list[Diagnostic] = diagnose(manager, locations)
        if arguments.json:
            print(json.dumps(checks, indent=2))
        else:
            for check in checks:
                print(f"{'OK' if check['ok'] else 'FAIL'} {check['check']}: {check['detail']}")
        return 0 if all(check["ok"] for check in checks) else 1
    store: Store = Store(locations.state)
    try:
        if isinstance(arguments, Submit):
            request: Submit = validated_submission(arguments)
            manager.ready()
            # Refuse silent acceptance into an unserviced queue.
            manager.command(["systemctl", "--user", "is-active", "--quiet", "fsched.service"])
            resources: Resources = effective_resources(sharing_count())
            cpu: float
            memory: int
            cpu, memory = allocation(budget_for(resources), request.cpu, request.memory)
            print(store.submit(request, cpu, memory))
        elif isinstance(arguments, ListJobs):
            jobs: list[Job] = store.jobs(arguments.all)
            if arguments.json:
                print(json.dumps(jobs, indent=2))
            else:
                for job in jobs:
                    print(
                        f"{job['id']} {job['state']:10} cpu={job['cpu']} "
                        f"memory={job['memory']} {job['reason']}"
                    )
        elif isinstance(arguments, Inspect):
            inspected: Job = store.get(arguments.job_id)
            print(
                json.dumps(
                    {
                        **inspected,
                        "argv": json.loads(str(inspected["argv"])),
                        "unit": unit_name(arguments.job_id),
                        "logs": f"fsched logs {arguments.job_id}",
                    },
                    indent=2,
                )
            )
        elif isinstance(arguments, Cancel):
            cancelled: Job = store.cancel(arguments.job_id)
            print(f"{cancelled['id']} {cancelled['state']} cancellation_requested")
        elif isinstance(arguments, Logs):
            store.get(arguments.job_id)
            command: list[str] = [
                "journalctl",
                "--user",
                "--unit",
                unit_name(arguments.job_id),
                "--no-pager",
                "--output=short-iso",
            ]
            if arguments.follow:
                command.append("--follow")
            return subprocess.call(command)
        elif isinstance(arguments, Daemon):
            daemon(store, manager, locations.state, arguments.once)
        elif isinstance(arguments, Execute):
            execute_job(store, arguments.job_id)
        return 0
    finally:
        store.close()

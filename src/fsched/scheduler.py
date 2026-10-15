"""FIFO admission and restart reconciliation of durable queue intent.

TODO(AI-GENERATED): Review cancellation and process-crash races on a real manager.
"""

from __future__ import annotations

import fcntl
import logging
import os
import signal
import time
from pathlib import Path
from types import FrameType

from fsched.models import TERMINAL, Budget, Resources
from fsched.paths import secure_file
from fsched.policy import admission_reason, budget_for
from fsched.probes import effective_resources, sharing_count
from fsched.store import Job, Store
from fsched.systemd import Systemd

LOGGER: logging.Logger = logging.getLogger(__name__)


def reconcile(store: Store, manager: Systemd) -> None:
    """Resolve active records from authoritative systemd state before admission.

    :param store: Open durable queue connection.
    :param manager: User-manager adapter, injectable for tests.
    :return: None; persists outcomes and performs requested cancellation.
    TODO(AI-GENERATED): Review ambiguous dispatch and reboot outcomes.
    """
    for job in store.reconcilable():
        if job["state"] in TERMINAL and not job["released"]:
            release_terminal(store, manager, str(job["id"]))
            continue
        if job["state"] not in {"starting", "running"}:
            continue
        identifier: str = str(job["id"])
        status: dict[str, str] = manager.status(identifier)
        missing: bool = status.get("LoadState") == "not-found"
        if job["cancel_requested"]:
            if not missing:
                manager.stop(identifier)
            store.update(identifier, state="cancelled", finished=time.time(), reason="")
            release_terminal(store, manager, identifier)
            continue
        if missing:
            store.update(
                identifier,
                state="failed",
                finished=time.time(),
                reason="unit lost or dispatch interrupted; not automatically replayed",
                released=1,
            )
            continue
        substate: str = status.get("SubState", "")
        result: str = status.get("Result", "")
        if substate in {"running", "start", "start-pre", "start-post"}:
            store.update(identifier, state="running")
            continue
        if substate not in {"exited", "dead", "failed"}:
            raise RuntimeError(f"unrecognized unit state for {identifier}: {status}")
        outcome: str = "failed"
        if result == "timeout":
            outcome = "timed_out"
        elif result == "success" and status.get("ExecMainStatus") == "0" and substate == "exited":
            outcome = "succeeded"
        store.update(
            identifier,
            state=outcome,
            finished=time.time(),
            result=result,
            exit_status=f"{status.get('ExecMainCode', '')}:{status.get('ExecMainStatus', '')}",
            reason="",
        )
        release_terminal(store, manager, identifier)


def release_terminal(store: Store, manager: Systemd, identifier: str) -> None:
    """Retry terminal-unit cleanup after crashes before releasing reservations.

    :param store: Durable queue with a terminal outcome already recorded.
    :param manager: User-manager adapter.
    :param identifier: Completed job identifier.
    :return: None; marks cleanup complete only after the unit is gone/stopped.
    TODO(AI-GENERATED): Review crash recovery between outcome and cleanup.
    """
    status: dict[str, str] = manager.status(identifier)
    if status.get("LoadState") != "not-found":
        manager.release(identifier)
    store.update(identifier, released=1)


def tick(store: Store, manager: Systemd, resources: Resources | None = None) -> None:
    """Reconcile and admit FIFO work under verified aggregate limits.

    :param store: Open queue, with the daemon lock held by the caller.
    :param manager: User-manager adapter.
    :param resources: Measured capacity/headroom; None probes after reconciliation.
    :return: None; starts eligible services and records queue reasons.
    TODO(AI-GENERATED): Review memory-ceiling transition safety.
    """
    reconcile(store, manager)
    measured: Resources = (
        resources if resources is not None else effective_resources(sharing_count())
    )
    budget: Budget = budget_for(measured)
    active: list[Job] = [job for job in store.jobs() if job["state"] in {"starting", "running"}]
    reserved_cpu: float = sum(float(str(job["cpu"])) for job in active)
    reserved_memory: int = sum(int(str(job["memory"])) for job in active)
    # Never shrink a hard memory limit beneath existing reservations. Stop new
    # admission until active work drains, then converge to the stricter policy.
    applied: Budget = Budget(
        cpu=budget.cpu,
        memory=max(budget.memory, reserved_memory),
        reserve=budget.reserve,
        high=budget.memory * 9 // 10,
    )
    manager.configure(applied)
    available: int = measured.available
    blocked: bool = False
    for job in store.jobs():
        if job["state"] != "queued":
            continue
        identifier: str = str(job["id"])
        if blocked:
            store.update(identifier, reason="waiting behind earlier queued job (FIFO)")
            continue
        cpu: float = float(str(job["cpu"]))
        memory: int = int(str(job["memory"]))
        reason: str = admission_reason(
            budget, available, cpu, memory, reserved_cpu, reserved_memory
        )
        if reason:
            store.update(identifier, reason=reason)
            blocked = True
            continue
        if not store.claim(identifier):
            continue
        # Persisted starting state is deliberately retained if the start call
        # fails ambiguously. Reconciliation decides; it must never retry blindly.
        manager.start(identifier, cpu, memory, int(str(job["duration"])))
        store.update(identifier, state="running", reason="")
        reserved_cpu += cpu
        reserved_memory += memory
        available -= memory


def daemon(store: Store, manager: Systemd, directory: Path, once: bool = False) -> None:
    """Run the serialized queue worker until signalled or one cycle completes.

    :param store: Open queue owned by this process.
    :param manager: User-manager adapter.
    :param directory: Validated private state directory for the singleton lock.
    :param once: Execute only one cycle, useful for diagnostics/tests.
    :return: None; gracefully exits after SIGTERM or SIGINT.
    :raises RuntimeError: If another worker holds the lock or the manager is absent.
    TODO(AI-GENERATED): Review service restart and signal behavior.
    """
    descriptor: int = secure_file(directory / "daemon.lock")
    stopping: bool = False

    def request_stop(signum: int, frame: FrameType | None) -> None:
        """Request an orderly exit after the current bounded operation.

        :param signum: Delivered termination or interrupt signal number.
        :param frame: Interrupted frame, unused.
        :return: None; updates the enclosing stop flag.
        TODO(AI-GENERATED): Review graceful shutdown.
        """
        nonlocal stopping
        stopping = True

    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another fsched daemon holds the queue lock") from exc
        manager.ready()
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        while not stopping:
            try:
                tick(store, manager)
            except (OSError, ValueError, RuntimeError) as exc:
                LOGGER.error("scheduler_cycle_failed reason=%s", exc)
                if once:
                    raise
            if once:
                return
            for _ in range(10):
                if stopping:
                    break
                time.sleep(0.5)
    finally:
        os.close(descriptor)

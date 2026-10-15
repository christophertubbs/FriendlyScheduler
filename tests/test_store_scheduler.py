"""Durability, cancellation, FIFO and crash-reconciliation stress cases.

TODO(AI-GENERATED): Review lifecycle invariants under real process concurrency.
"""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import pytest

from fsched.models import GIB, Resources, Submit
from fsched.scheduler import reconcile, tick
from fsched.store import Store
from tests.conftest import FakeManager


def test_durable_literal_submission(store: Store, submission: Submit) -> None:
    """Serialized argv is data and survives reopening SQLite.

    :param store: Private isolated queue.
    :param submission: Valid harmless command.
    :return: None; asserts literal roundtrip and private database mode.
    TODO(AI-GENERATED): Review durability evidence.
    """
    argv: tuple[str, ...] = ("echo", "'\"", "$PATH", "%n", "a\nb", "é", "")
    identifier: str = store.submit(Submit(argv, submission.cwd), 1, GIB)
    assert json.loads(str(store.get(identifier)["argv"])) == list(argv)
    assert len(identifier) == 32
    assert store.connection.execute("PRAGMA synchronous").fetchone()[0] == 2


def test_cancel_before_claim(store: Store, submission: Submit) -> None:
    """A durable cancellation prevents queued work from being claimed.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts idempotent cancellation and no dispatch claim.
    TODO(AI-GENERATED): Review cancellation transaction ordering.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.cancel(identifier)
    store.cancel(identifier)
    assert not store.claim(identifier)
    assert store.get(identifier)["state"] == "cancelled"
    assert store.jobs() == []
    assert len(store.jobs(True)) == 1


def test_fifo_and_capacity(store: Store, submission: Submit) -> None:
    """Only fitting FIFO work starts; later small jobs do not jump the queue.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts aggregate reservation and blocked reason.
    TODO(AI-GENERATED): Review fairness policy.
    """
    first: str = store.submit(submission, 2, GIB)
    second: str = store.submit(submission, 2, GIB)
    third: str = store.submit(submission, 0.1, GIB)
    manager: FakeManager = FakeManager()
    tick(store, manager, Resources(4, 16 * GIB, 15 * GIB, 1))
    assert manager.started == [first]
    assert store.get(second)["state"] == "queued"
    assert "CPU" in str(store.get(second)["reason"])
    assert store.get(third)["state"] == "queued"


def test_ambiguous_start_not_replayed(store: Store, submission: Submit) -> None:
    """A bus failure after service creation never launches the command twice.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts restart reconciliation adopts the existing unit.
    TODO(AI-GENERATED): Review exactly-once limitations.
    """
    identifier: str = store.submit(submission, 1, GIB)
    manager: FakeManager = FakeManager()
    manager.fail_start = True
    with pytest.raises(RuntimeError):
        tick(store, manager, Resources(8, 16 * GIB, 15 * GIB, 1))
    assert store.get(identifier)["state"] == "starting"
    manager.fail_start = False
    tick(store, manager, Resources(8, 16 * GIB, 15 * GIB, 1))
    assert manager.started == [identifier]
    assert store.get(identifier)["state"] == "running"


@pytest.mark.parametrize(
    "result,status,substate,expected",
    [
        ("success", "0", "exited", "succeeded"),
        ("exit-code", "3", "failed", "failed"),
        ("timeout", "15", "failed", "timed_out"),
        ("oom-kill", "9", "failed", "failed"),
        ("signal", "9", "failed", "failed"),
        ("success", "0", "dead", "failed"),
    ],
)
def test_outcomes(
    store: Store, submission: Submit, result: str, status: str, substate: str, expected: str
) -> None:
    """systemd outcomes preserve timeouts and failures instead of fabricating success.

    :param store: Private queue.
    :param submission: Harmless command.
    :param result: systemd Result property.
    :param status: Exit code or signal number.
    :param substate: Service substate.
    :param expected: Durable terminal outcome.
    :return: None; asserts persistence before release.
    TODO(AI-GENERATED): Review result mapping.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    manager: FakeManager = FakeManager()
    manager.states[identifier] = {
        "LoadState": "loaded",
        "SubState": substate,
        "Result": result,
        "ExecMainStatus": status,
        "ExecMainCode": "1",
    }
    reconcile(store, manager)
    assert store.get(identifier)["state"] == expected
    assert store.get(identifier)["result"] == result
    assert manager.stopped == [identifier]


def test_lost_unit_not_replayed(store: Store, submission: Submit) -> None:
    """A reboot or lost dispatch marks interruption instead of rerunning work.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts missing-unit failure.
    TODO(AI-GENERATED): Review interruption handling.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    reconcile(store, FakeManager())
    assert store.get(identifier)["state"] == "failed"
    assert "not automatically replayed" in str(store.get(identifier)["reason"])


def test_running_cancel(store: Store, submission: Submit) -> None:
    """Cancellation intent survives restart and stops the entire retained service.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts cancellation convergence.
    TODO(AI-GENERATED): Review dispatch/cancel race.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    manager: FakeManager = FakeManager()
    manager.start(identifier, 1, GIB, 20)
    store.cancel(identifier)
    reconcile(store, manager)
    assert manager.stopped == [identifier]
    assert store.get(identifier)["state"] == "cancelled"


def test_shrink_does_not_kill_memory_reservations(store: Store, submission: Submit) -> None:
    """A new sharing estimate blocks admission without shrinking below live promises.

    :param store: Private queue.
    :param submission: Harmless command.
    :return: None; asserts safe hard-limit transition.
    TODO(AI-GENERATED): Review convergence after jobs drain.
    """
    first: str = store.submit(submission, 1, 6 * GIB)
    store.claim(first)
    manager: FakeManager = FakeManager()
    manager.start(first, 1, 6 * GIB, 20)
    pending: str = store.submit(submission, 1, GIB)
    tick(store, manager, Resources(16, 16 * GIB, 8 * GIB, 7))
    assert manager.budgets[-1].memory == 6 * GIB
    assert manager.budgets[-1].high == (2 * GIB) * 9 // 10
    assert store.get(pending)["state"] == "queued"


def concurrent_submit(directory: Path, submission: Submit) -> str:
    """Open an independent client connection and submit one job.

    :param directory: Existing private queue directory.
    :param submission: Harmless command.
    :return: Unique persisted job ID.
    TODO(AI-GENERATED): Review connection cleanup on error.
    """
    client: Store = Store(directory)
    try:
        return client.submit(submission, 0.1, GIB)
    finally:
        client.close()


def test_concurrent_submitters(tmp_path: Path, submission: Submit) -> None:
    """Independent concurrent clients lose neither jobs nor identifiers.

    :param tmp_path: Temporary state root.
    :param submission: Harmless command.
    :return: None; asserts all writes survive concurrent connections.
    TODO(AI-GENERATED): Review transaction contention.
    """
    directory: Path = tmp_path / "concurrent"
    initial: Store = Store(directory)
    initial.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures: list[Future[str]] = [
            pool.submit(concurrent_submit, directory, submission) for _ in range(32)
        ]
        identifiers: list[str] = [future.result() for future in futures]
    client: Store = Store(directory)
    try:
        assert len(set(identifiers)) == len(client.jobs()) == 32
    finally:
        client.close()


def test_terminal_cleanup_retried_after_crash(store: Store, submission: Submit) -> None:
    """Outcome persistence before a crash cannot leak a retained service forever.

    :param store: Private queue.
    :param submission: Harmless submission.
    :return: None; asserts restart cleanup and durable release acknowledgement.
    TODO(AI-GENERATED): Review terminal cleanup crash window.
    """
    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    manager: FakeManager = FakeManager()
    manager.start(identifier, 1, GIB, 30)
    store.update(identifier, state="succeeded")
    reconcile(store, manager)
    assert manager.stopped == [identifier]
    assert store.get(identifier)["released"] == 1
    reconcile(store, manager)
    assert manager.stopped == [identifier]


def test_enforcement_failure_never_dispatches(
    store: Store, submission: Submit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Queued work remains intact if aggregate limit verification fails.

    :param store: Private queue.
    :param submission: Harmless command.
    :param monkeypatch: Scoped limit failure injection.
    :return: None; asserts zero job starts.
    TODO(AI-GENERATED): Review fail-closed admission ordering.
    """
    from unittest.mock import MagicMock

    identifier: str = store.submit(submission, 1, GIB)
    manager: FakeManager = FakeManager()
    monkeypatch.setattr(manager, "configure", MagicMock(side_effect=RuntimeError("no delegation")))
    with pytest.raises(RuntimeError, match="delegation"):
        tick(store, manager, Resources(8, 16 * GIB, 15 * GIB, 1))
    assert manager.started == []
    assert store.get(identifier)["state"] == "queued"


def test_cancel_survives_resource_probe_failure(
    store: Store, submission: Submit, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unavailable admission measurements must not prevent running cancellation.

    :param store: Private queue.
    :param submission: Harmless command.
    :param monkeypatch: Scoped failed resource probe.
    :return: None; asserts cancellation precedes admission-only prerequisites.
    TODO(AI-GENERATED): Review cancellation availability under pressure.
    """
    from unittest.mock import MagicMock

    identifier: str = store.submit(submission, 1, GIB)
    store.claim(identifier)
    manager: FakeManager = FakeManager()
    manager.start(identifier, 1, GIB, 30)
    store.cancel(identifier)
    monkeypatch.setattr("fsched.scheduler.sharing_count", MagicMock(return_value=1))
    monkeypatch.setattr(
        "fsched.scheduler.effective_resources",
        MagicMock(side_effect=ValueError("unreadable resource counters")),
    )
    with pytest.raises(ValueError, match="counters"):
        tick(store, manager)
    assert manager.stopped == [identifier]
    assert store.get(identifier)["state"] == "cancelled"

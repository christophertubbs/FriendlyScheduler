"""Private temporary state fixtures and a deterministic systemd boundary fake.

TODO(AI-GENERATED): Review whether fake behavior matches real systemd.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from fsched.models import Budget, Submit
from fsched.store import Store
from fsched.systemd import Systemd


class FakeManager(Systemd):
    """Model retained services and record resource/cancellation requests.

    TODO(AI-GENERATED): Review real-manager integration separately.
    """

    def __init__(self) -> None:
        """Initialize isolated in-memory unit state.

        :return: None; no external operations occur.
        TODO(AI-GENERATED): Review fake defaults.
        """
        self.states: dict[str, dict[str, str]] = {}
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.budgets: list[Budget] = []
        self.fail_start: bool = False

    def ready(self) -> None:
        """Accept the fake bus connection.

        :return: None; no external operation.
        TODO(AI-GENERATED): Review fake scope.
        """

    def configure(self, budget: Budget) -> None:
        """Record the aggregate limit requested by admission.

        :param budget: CPU and memory aggregate ceiling.
        :return: None; adds one recorded configuration.
        TODO(AI-GENERATED): Review enforcement tests separately.
        """
        self.budgets.append(budget)

    def start(self, identifier: str, cpu: float, memory: int, duration: int) -> None:
        """Simulate service creation, optionally an ambiguous transport failure.

        :param identifier: Job ID.
        :param cpu: Requested CPU equivalents.
        :param memory: Requested bytes.
        :param duration: Runtime seconds.
        :return: None; records dispatch and running unit state.
        TODO(AI-GENERATED): Review fake transition realism.
        """
        self.started.append(identifier)
        self.states[identifier] = {
            "LoadState": "loaded",
            "SubState": "running",
            "Result": "success",
        }
        if self.fail_start:
            raise RuntimeError("ambiguous bus disconnect after start")

    def status(self, identifier: str) -> dict[str, str]:
        """Return fake state or missing-unit evidence.

        :param identifier: Job ID.
        :return: Copy of properties.
        TODO(AI-GENERATED): Review absent-unit handling.
        """
        return self.states.get(identifier, {"LoadState": "not-found"}).copy()

    def stop(self, identifier: str) -> None:
        """Record descendant-group cancellation.

        :param identifier: Job ID.
        :return: None; records a stop.
        TODO(AI-GENERATED): Review stop sequencing.
        """
        self.stopped.append(identifier)
        self.states.pop(identifier, None)

    def release(self, identifier: str) -> None:
        """Remove fake retained state after outcome persistence.

        :param identifier: Job ID.
        :return: None; records release as a stop.
        TODO(AI-GENERATED): Review outcome ordering tests.
        """
        self.stop(identifier)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """Provide isolated durable state and always close its connection.

    :param tmp_path: pytest private temporary directory.
    :return: Iterator yielding one open Store.
    TODO(AI-GENERATED): Review fixture cleanup.
    """
    instance: Store = Store(tmp_path / "state")
    yield instance
    instance.close()


@pytest.fixture
def submission(tmp_path: Path) -> Submit:
    """Provide a harmless literal command submission.

    :param tmp_path: Existing private cwd.
    :return: Typed command request.
    TODO(AI-GENERATED): Review command portability.
    """
    return Submit(argv=("/usr/bin/true",), cwd=tmp_path)

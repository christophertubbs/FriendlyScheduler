"""Allocation boundaries and adversarial numeric cases.

TODO(AI-GENERATED): Review resource-policy acceptance coverage.
"""

from __future__ import annotations

import math

import pytest

from fsched.models import GIB, Budget, Resources
from fsched.policy import admission_reason, allocation, budget_for


@pytest.mark.parametrize("users", list(range(100)))
def test_sharing_monotonic(users: int) -> None:
    """Increasing sharing never increases ceilings or consumes the reserve.

    :param users: Other-user count.
    :return: None; asserts resource bounds and monotonicity.
    TODO(AI-GENERATED): Review fairness assumptions.
    """
    capacity: Resources = Resources(16, int(70.3 * GIB), 50 * GIB, users)
    current: Budget = budget_for(capacity)
    following: Budget = budget_for(Resources(16, capacity.memory, 50 * GIB, users + 1))
    assert 0 < following.cpu <= current.cpu < capacity.cpu
    assert 0 < following.memory <= current.memory <= capacity.memory - current.reserve


@pytest.mark.parametrize(
    "cpu,memory,available,others",
    [
        (math.nan, GIB, GIB, 1),
        (math.inf, GIB, GIB, 1),
        (0, GIB, GIB, 1),
        (-1, GIB, GIB, 1),
        (2, 0, 0, 1),
        (2, GIB, -1, 1),
        (2, GIB, GIB, -1),
        (0.001, GIB, GIB, 1),
        (2, 1024, 1024, 1),
    ],
)
def test_invalid_capacity(cpu: float, memory: int, available: int, others: int) -> None:
    """Invalid measurements fail closed rather than manufacturing capacity.

    :param cpu: Adversarial effective CPU value.
    :param memory: Measured capacity bytes.
    :param available: Measured headroom bytes.
    :param others: Other-user count.
    :return: None; asserts rejection.
    TODO(AI-GENERATED): Review invalid-value coverage.
    """
    with pytest.raises(ValueError):
        budget_for(Resources(cpu, memory, available, others))


def test_small_parent_quota() -> None:
    """Fractional capacity is never rounded up to a full core or GiB.

    :return: None; asserts small-parent bounds.
    TODO(AI-GENERATED): Review minimum viable resource sizing.
    """
    budget: Budget = budget_for(Resources(0.5, GIB, GIB, 0))
    assert allocation(budget, None, None) == (0.25, GIB // 2)


@pytest.mark.parametrize(
    "cpu,memory",
    [(math.nan, GIB), (math.inf, GIB), (-1, GIB), (0, GIB), (9, GIB), (1, 0), (1, 40 * GIB)],
)
def test_override_rejection(cpu: float, memory: int) -> None:
    """Overrides cannot bypass conservative ceilings.

    :param cpu: Requested CPU equivalents.
    :param memory: Requested bytes.
    :return: None; asserts invalid override rejection.
    TODO(AI-GENERATED): Review override constraints.
    """
    with pytest.raises(ValueError):
        allocation(Budget(8, 35 * GIB, 14 * GIB), cpu, memory)


@pytest.mark.parametrize(
    "available,cpu,memory,used_cpu,used_memory,reason",
    [
        (30 * GIB, 2, 4 * GIB, 6, 20 * GIB, ""),
        (30 * GIB, 3, 4 * GIB, 6, 20 * GIB, "CPU"),
        (30 * GIB, 2, 20 * GIB, 6, 20 * GIB, "aggregate memory"),
        (15 * GIB, 2, 4 * GIB, 0, 0, "available memory"),
    ],
)
def test_admission(
    available: int, cpu: float, memory: int, used_cpu: float, used_memory: int, reason: str
) -> None:
    """Reservation and live memory gates remain independent.

    :param available: Measured available bytes.
    :param cpu: Incoming CPU reservation.
    :param memory: Incoming memory reservation.
    :param used_cpu: Existing CPU reservations.
    :param used_memory: Existing memory reservations.
    :param reason: Expected reason substring or empty success marker.
    :return: None; asserts admission behavior.
    TODO(AI-GENERATED): Review double-counting regression coverage.
    """
    result: str = admission_reason(
        Budget(8, 35 * GIB, 14 * GIB), available, cpu, memory, used_cpu, used_memory
    )
    assert (reason in result) if reason else result == ""

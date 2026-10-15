"""Pure conservative allocation policy; no kernel or subprocess side effects.

TODO(AI-GENERATED): Review numerical policy on representative shared hosts.
"""

from __future__ import annotations

import math

from fsched.models import GIB, Budget, Resources


def budget_for(resources: Resources) -> Budget:
    """Calculate aggregate ceilings that shrink with recent sharing.

    :param resources: Positive finite capacity and nonnegative availability/users.
    :return: CPU, memory and interactive reserve; memory values are bytes.
    :raises ValueError: For invalid or unusably small measurements.
    TODO(AI-GENERATED): Review fractional-CPU and small-memory behavior.
    """
    if (
        not math.isfinite(resources.cpu)
        or resources.cpu <= 0
        or resources.memory <= 0
        or resources.available < 0
        or resources.others < 0
    ):
        raise ValueError("invalid resource measurements; refusing admission")
    shares: int = max(2, resources.others + 1)
    reserve: int = min(max(2 * GIB, resources.memory // 5), resources.memory // 2)
    memory: int = min(
        resources.memory // shares, resources.memory * 7 // 10, resources.memory - reserve
    )
    if memory < 16 * 1024**2 or resources.cpu / shares < 0.01:
        raise ValueError("effective capacity is too small to safely schedule jobs")
    return Budget(
        cpu=min(resources.cpu / shares, resources.cpu * 0.75), memory=memory, reserve=reserve
    )


def allocation(budget: Budget, cpu: float | None, memory: int | None) -> tuple[float, int]:
    """Resolve overrides or small automatic per-job defaults.

    :param budget: Current protective aggregate ceiling.
    :param cpu: Requested CPU equivalents, or None for up to two.
    :param memory: Requested bytes, or None for up to four GiB.
    :return: Validated CPU and memory reservation.
    :raises ValueError: For invalid requests or requests exceeding current ceiling.
    TODO(AI-GENERATED): Review override policy.
    """
    chosen_cpu: float = min(2.0, budget.cpu) if cpu is None else cpu
    chosen_memory: int = min(4 * GIB, budget.memory) if memory is None else memory
    if not math.isfinite(chosen_cpu) or not 0.01 <= chosen_cpu <= budget.cpu:
        raise ValueError(f"CPU request exceeds current safe ceiling ({budget.cpu:.2f})")
    if not 0 < chosen_memory <= budget.memory:
        raise ValueError(f"memory request exceeds current safe ceiling ({budget.memory} bytes)")
    return chosen_cpu, chosen_memory


def admission_reason(
    budget: Budget,
    available: int,
    cpu: float,
    memory: int,
    reserved_cpu: float,
    reserved_memory: int,
) -> str:
    """Explain why a queued reservation must wait, or allow admission.

    :param budget: Protective aggregate ceilings and interactive reserve.
    :param available: Current effective available memory in bytes.
    :param cpu: New job's CPU equivalents.
    :param memory: New job's reserved bytes.
    :param reserved_cpu: CPU equivalents already promised to active jobs.
    :param reserved_memory: Bytes already promised to active jobs.
    :return: Empty string if admissible, otherwise an actionable blocked reason.
    TODO(AI-GENERATED): Review reservation/headroom accounting.
    """
    if reserved_cpu + cpu > budget.cpu + 1e-9:
        return "waiting for aggregate CPU budget"
    if reserved_memory + memory > budget.memory:
        return "waiting for aggregate memory budget"
    # Current availability already excludes resident memory: only add the new job,
    # not every running reservation, when checking observed free headroom.
    if memory + budget.reserve > available:
        return "waiting for available memory and interactive reserve"
    return ""

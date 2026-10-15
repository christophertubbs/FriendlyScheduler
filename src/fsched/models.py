"""Typed resource and command contracts independent of CLI and systemd.

TODO(AI-GENERATED): Review resource assumptions before production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

GIB: int = 1024**3
TERMINAL: tuple[str, ...] = ("succeeded", "failed", "cancelled", "timed_out")


@dataclass(frozen=True)
class Resources:
    """Effective host capacity and current headroom, including ancestor ceilings.

    cpu: CPU equivalents, possibly fractional; memory/available: bytes.
    others: distinct other recent users, or conservative fallback count.
    TODO(AI-GENERATED): Review capacity measurement assumptions.
    """

    cpu: float
    memory: int
    available: int
    others: int


@dataclass(frozen=True)
class Budget:
    """Aggregate job allowances; memory/reserve/high are bytes, cpu is equivalents.

    high optionally lowers soft memory pressure while existing hard reservations drain.

    TODO(AI-GENERATED): Review protection policy.
    """

    cpu: float
    memory: int
    reserve: int
    high: Optional[int] = None


@dataclass(frozen=True)
class Submit:
    """Submission inputs; argv is literal, memory bytes, duration seconds.

    None cpu/memory requests choose policy defaults; cwd is an absolute directory.
    TODO(AI-GENERATED): Review submission contract.
    """

    argv: tuple[str, ...]
    cwd: Path
    cpu: Optional[float] = None
    memory: Optional[int] = None
    duration: int = 86400


@dataclass(frozen=True)
class ListJobs:
    """List active jobs, or history when all is true; json selects machine output.

    TODO(AI-GENERATED): Review command contract.
    """

    all: bool = False
    json: bool = False


@dataclass(frozen=True)
class Inspect:
    """Select one job by generated identifier, optionally producing JSON.

    TODO(AI-GENERATED): Review command contract.
    """

    job_id: str
    json: bool = False


@dataclass(frozen=True)
class Cancel:
    """Request durable cancellation of one job and all service descendants.

    TODO(AI-GENERATED): Review cancellation semantics.
    """

    job_id: str


@dataclass(frozen=True)
class Logs:
    """Read journald output for job_id; follow streams future entries.

    TODO(AI-GENERATED): Review log exposure and retention.
    """

    job_id: str
    follow: bool = False


@dataclass(frozen=True)
class Doctor:
    """Run readiness probes; json selects machine-readable diagnostics.

    TODO(AI-GENERATED): Review readiness coverage.
    """

    json: bool = False


@dataclass(frozen=True)
class Daemon:
    """Run the queue worker; once performs one reconciliation/admission cycle.

    TODO(AI-GENERATED): Review lifecycle contract.
    """

    once: bool = False


@dataclass(frozen=True)
class Execute:
    """Internal fixed runner for a persisted job identifier.

    TODO(AI-GENERATED): Review execution boundary.
    """

    job_id: str


Arguments = Union[Submit, ListJobs, Inspect, Cancel, Logs, Doctor, Daemon, Execute]

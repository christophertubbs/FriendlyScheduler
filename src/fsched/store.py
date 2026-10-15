"""Transactional private SQLite queue and durable lifecycle records.

TODO(AI-GENERATED): Review crash consistency and migration behavior.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Union

from fsched.models import Submit
from fsched.parsing import job_id_value
from fsched.paths import private_directory, secure_file

Value = Union[str, int, float, None]
Job = dict[str, Value]


class Store:
    """Own one SQLite connection; all writes are transactional and bounded.

    TODO(AI-GENERATED): Review lifecycle invariants.
    """

    def __init__(self, directory: Path) -> None:
        """Open private durable queue state.

        :param directory: Owner-only XDG state directory.
        :return: None; creates schema and opens a database connection.
        TODO(AI-GENERATED): Review state initialization.
        """
        private_directory(directory)
        database: Path = directory / "queue.sqlite3"
        descriptor: int = secure_file(database)
        os.close(descriptor)
        self.connection: sqlite3.Connection = sqlite3.connect(database, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=DELETE")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("BEGIN IMMEDIATE")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, argv TEXT NOT NULL, cwd TEXT NOT NULL,
            cpu REAL NOT NULL, memory INTEGER NOT NULL, duration INTEGER NOT NULL,
            state TEXT NOT NULL, created REAL NOT NULL, started REAL, finished REAL,
            reason TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
            exit_status TEXT NOT NULL DEFAULT '', cancel_requested INTEGER NOT NULL DEFAULT 0,
            released INTEGER NOT NULL DEFAULT 0
        )""")
        columns: set[str] = {row[1] for row in self.connection.execute("PRAGMA table_info(jobs)")}
        if "released" not in columns:
            self.connection.execute(
                "ALTER TABLE jobs ADD COLUMN released INTEGER NOT NULL DEFAULT 0"
            )
        self.connection.commit()

    def close(self) -> None:
        """Release the SQLite connection.

        :return: None; no further operations may use this instance.
        TODO(AI-GENERATED): Review ownership contract.
        """
        self.connection.close()

    def submit(self, request: Submit, cpu: float, memory: int) -> str:
        """Persist literal argv and resolved allocations before acknowledging.

        :param request: Validated command, cwd and runtime.
        :param cpu: Positive reserved CPU equivalents.
        :param memory: Positive reserved memory bytes.
        :return: New random 32-hex job identifier.
        TODO(AI-GENERATED): Review submission atomicity.
        """
        identifier: str = uuid.uuid4().hex
        with self.connection:
            self.connection.execute(
                "INSERT INTO jobs (id,argv,cwd,cpu,memory,duration,state,created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    json.dumps(request.argv),
                    str(request.cwd),
                    cpu,
                    memory,
                    request.duration,
                    "queued",
                    time.time(),
                ),
            )
        return identifier

    def get(self, identifier: str) -> Job:
        """Read one job without interpreting argv as executable code.

        :param identifier: Generated job ID.
        :return: Stored record including serialized argv.
        :raises ValueError: If syntax is invalid or job is unknown.
        TODO(AI-GENERATED): Review record contract.
        """
        job_id_value(identifier)
        row: sqlite3.Row | None = self.connection.execute(
            "SELECT * FROM jobs WHERE id=?",
            (identifier,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown job: {identifier}")
        return dict(row)

    def jobs(self, all_jobs: bool = False) -> list[Job]:
        """Read jobs in deterministic FIFO order.

        :param all_jobs: Include terminal history when true.
        :return: Ordered independent record dictionaries.
        TODO(AI-GENERATED): Review history scaling.
        """
        condition: str = (
            ""
            if all_jobs
            else ("WHERE state NOT IN ('succeeded','failed','cancelled','timed_out') ")
        )
        rows: list[sqlite3.Row] = self.connection.execute(
            f"SELECT * FROM jobs {condition}ORDER BY created, rowid",
        ).fetchall()
        return [dict(row) for row in rows]

    def reconcilable(self) -> list[Job]:
        """Read only active jobs and terminal units still needing cleanup.

        :return: FIFO records excluding already-released terminal history.
        TODO(AI-GENERATED): Review large-queue behavior and index needs.
        """
        rows: list[sqlite3.Row] = self.connection.execute(
            "SELECT * FROM jobs WHERE released=0 "
            "OR state NOT IN ('succeeded','failed','cancelled','timed_out') "
            "ORDER BY created,rowid",
        ).fetchall()
        return [dict(row) for row in rows]

    def update(self, identifier: str, **values: Value) -> None:
        """Update allowlisted lifecycle fields atomically.

        :param identifier: Existing generated job ID.
        :param values: State/result/timestamp/cancellation fields only.
        :return: None; commits a durable lifecycle transition.
        :raises ValueError: For unsupported columns or unknown jobs.
        TODO(AI-GENERATED): Review transition access boundaries.
        """
        self.get(identifier)
        allowed: set[str] = {
            "state",
            "started",
            "finished",
            "reason",
            "result",
            "exit_status",
            "cancel_requested",
            "released",
        }
        if not values or not set(values) <= allowed:
            raise ValueError("unsupported job update")
        assignments: str = ",".join(f"{column}=?" for column in values)
        with self.connection:
            self.connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id=?",
                (*values.values(), identifier),
            )

    def claim(self, identifier: str) -> bool:
        """Atomically claim queued work unless cancellation was requested.

        :param identifier: Queued generated job identifier.
        :return: True only when this transaction claimed dispatch intent.
        TODO(AI-GENERATED): Review admission/cancellation races.
        """
        with self.connection:
            cursor: sqlite3.Cursor = self.connection.execute(
                "UPDATE jobs SET state='starting',started=? WHERE id=? "
                "AND state='queued' AND cancel_requested=0",
                (time.time(), identifier),
            )
        return cursor.rowcount == 1

    def cancel(self, identifier: str) -> Job:
        """Persist cancellation intent without racing a dispatch claim.

        :param identifier: Existing generated job identifier.
        :return: Updated record; queued jobs become immediately cancelled.
        TODO(AI-GENERATED): Review concurrent state transitions.
        """
        self.get(identifier)
        with self.connection:
            self.connection.execute(
                "UPDATE jobs SET cancel_requested=1, "
                "released=CASE WHEN state='queued' THEN 1 ELSE released END, "
                "finished=CASE WHEN state='queued' THEN ? ELSE finished END, "
                "state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END "
                "WHERE id=? AND state NOT IN ('succeeded','failed','cancelled','timed_out')",
                (time.time(), identifier),
            )
        return self.get(identifier)

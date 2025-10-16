"""SQLite-backed signal repository for analytics and audits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import json
import sqlite3
import uuid


@dataclass(frozen=True)
class RecordedSignal:
    signal_id: str
    status: str
    created_at: datetime


class SignalRepository:
    """Persist signals (valid/invalid) and outcomes for Grafana/CSV exports."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT,
                    timeframe TEXT,
                    direction TEXT,
                    score INTEGER,
                    grade TEXT,
                    delta REAL,
                    conditions TEXT,
                    risk_reward REAL,
                    entry_price REAL,
                    target_price REAL,
                    stop_price REAL,
                    leverage REAL,
                    bet_pct REAL,
                    reasons TEXT,
                    metadata TEXT
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outcomes (
                    signal_id TEXT PRIMARY KEY,
                    resolved_at TEXT NOT NULL,
                    pnl REAL,
                    outcome TEXT,
                    notes TEXT,
                    FOREIGN KEY(signal_id) REFERENCES signals(id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outcome_jobs (
                    signal_id TEXT PRIMARY KEY,
                    scheduled_for TEXT NOT NULL,
                    FOREIGN KEY(signal_id) REFERENCES signals(id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE VIEW IF NOT EXISTS v_signals_latest AS
                SELECT
                    s.id AS signal_id,
                    s.created_at,
                    s.status,
                    s.symbol,
                    s.timeframe,
                    s.direction,
                    s.score,
                    s.grade,
                    s.delta,
                    s.risk_reward,
                    s.entry_price,
                    s.target_price,
                    s.stop_price,
                    s.leverage,
                    s.bet_pct,
                    s.reasons,
                    s.metadata,
                    o.resolved_at,
                    o.pnl,
                    o.outcome
                FROM signals s
                LEFT JOIN outcomes o ON o.signal_id = s.id;
                """
            )

    def record(
        self,
        *,
        status: str,
        symbol: Optional[str],
        timeframe: Optional[str],
        direction: Optional[str],
        score: Optional[int],
        grade: Optional[str],
        delta: Optional[float],
        risk_reward: Optional[float],
        conditions: Iterable[str] | None,
        trade_plan: Dict[str, Any] | None,
        reasons: Iterable[str] | None,
        metadata: Dict[str, Any] | None,
        created_at: datetime | None = None,
    ) -> RecordedSignal:
        when = created_at or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        signal_id = uuid.uuid4().hex
        plan = trade_plan or {}
        record = (
            signal_id,
            when.isoformat(),
            status,
            symbol,
            timeframe,
            direction,
            score,
            grade,
            delta,
            "|".join(conditions or []),
            risk_reward,
            plan.get("entry"),
            plan.get("target"),
            plan.get("stop"),
            plan.get("leverage"),
            plan.get("bet_pct"),
            "|".join(reasons or []),
            json.dumps(metadata or {}, ensure_ascii=False),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO signals (
                    id, created_at, status, symbol, timeframe, direction,
                    score, grade, delta, conditions, risk_reward,
                    entry_price, target_price, stop_price, leverage, bet_pct,
                    reasons, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                record,
            )
        return RecordedSignal(signal_id=signal_id, status=status, created_at=when)

    def schedule_outcome(self, signal_id: str, when: datetime) -> None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO outcome_jobs (signal_id, scheduled_for)
                VALUES (?, ?);
                """,
                (signal_id, when.isoformat()),
            )

    def record_outcome(
        self,
        *,
        signal_id: str,
        pnl: float,
        outcome: str,
        notes: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> None:
        when = resolved_at or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO outcomes (signal_id, resolved_at, pnl, outcome, notes)
                VALUES (?, ?, ?, ?, ?);
                """,
                (signal_id, when.isoformat(), pnl, outcome, notes),
            )
            self._conn.execute("DELETE FROM outcome_jobs WHERE signal_id = ?;", (signal_id,))

    def fetch_due_jobs(self, until: datetime) -> list[Dict[str, Any]]:
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        cursor = self._conn.execute(
            """
            SELECT
                s.id AS signal_id,
                s.created_at,
                s.symbol,
                s.timeframe,
                s.direction,
                s.entry_price,
                s.target_price,
                s.stop_price,
                s.metadata,
                o.scheduled_for
            FROM outcome_jobs o
            JOIN signals s ON s.id = o.signal_id
            WHERE o.scheduled_for <= ?
            """,
            (until.isoformat(),),
        )
        rows = cursor.fetchall()
        jobs: list[Dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            metadata_raw = payload.get("metadata")
            if isinstance(metadata_raw, str) and metadata_raw:
                try:
                    payload["metadata"] = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    payload["metadata"] = {}
            else:
                payload["metadata"] = {}
            jobs.append(payload)
        return jobs

    def export_csv(self, path: Path, status: Optional[str] = None) -> None:
        query = "SELECT * FROM v_signals_latest"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        cursor = self._conn.execute(query, params)
        columns = [col[0] for col in cursor.description]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(columns) + "\n")
            for row in cursor.fetchall():
                cells = []
                for value in row:
                    if value is None:
                        cells.append("")
                    elif isinstance(value, str) and "," in value:
                        cells.append(f"\"{value.replace('\"', '\"\"')}\"")
                    else:
                        cells.append(str(value))
                handle.write(",".join(cells) + "\n")

    def close(self) -> None:
        self._conn.close()


__all__ = ["SignalRepository", "RecordedSignal"]

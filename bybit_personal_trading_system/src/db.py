from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.models import ExecutionOrder, PositionState


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_order_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    side TEXT NOT NULL,
                    action TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL,
                    status TEXT NOT NULL,
                    exchange_order_id TEXT,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    qty REAL NOT NULL,
                    pnl REAL NOT NULL,
                    fee REAL NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_price REAL,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_pct REAL NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    total_equity REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    drawdown REAL NOT NULL,
                    note TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def has_order(self, client_order_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM orders WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
        return row is not None

    def insert_order(
        self,
        order: ExecutionOrder,
        status: str,
        exchange_order_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        raw_payload = payload or {}
        raw_payload.setdefault("order", asdict(order))
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO orders (
                    client_order_id, symbol, strategy_id, mode, side, action, qty, price,
                    status, exchange_order_id, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.client_order_id,
                    order.symbol,
                    order.strategy_id,
                    order.mode,
                    order.side,
                    order.action,
                    order.qty,
                    order.reference_price,
                    status,
                    exchange_order_id,
                    utc_now(),
                    json.dumps(raw_payload, ensure_ascii=False),
                ),
            )

    def upsert_position(self, position: PositionState) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO positions (
                    symbol, strategy_id, mode, side, qty, entry_price, stop_price,
                    opened_at, updated_at, status, risk_pct, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    strategy_id=excluded.strategy_id,
                    mode=excluded.mode,
                    side=excluded.side,
                    qty=excluded.qty,
                    entry_price=excluded.entry_price,
                    stop_price=excluded.stop_price,
                    opened_at=excluded.opened_at,
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    risk_pct=excluded.risk_pct,
                    payload=excluded.payload
                """,
                (
                    position.symbol,
                    position.strategy_id,
                    position.mode,
                    position.side,
                    position.qty,
                    position.entry_price,
                    position.stop_price,
                    position.opened_at.isoformat(),
                    position.updated_at.isoformat(),
                    position.status,
                    position.risk_pct,
                    json.dumps(position.metadata, ensure_ascii=False),
                ),
            )

    def close_position(self, symbol: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE positions
                SET status = 'closed', updated_at = ?
                WHERE symbol = ? AND status = 'open'
                """,
                (utc_now(), symbol),
            )

    def get_open_positions(self, mode: str | None = None) -> dict[str, PositionState]:
        query = "SELECT * FROM positions WHERE status = 'open'"
        params: tuple[Any, ...] = ()
        if mode:
            query += " AND mode = ?"
            params = (mode,)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        result: dict[str, PositionState] = {}
        for row in rows:
            result[row["symbol"]] = PositionState(
                symbol=row["symbol"],
                strategy_id=row["strategy_id"],
                mode=row["mode"],
                side=row["side"],
                qty=float(row["qty"]),
                entry_price=float(row["entry_price"]),
                stop_price=float(row["stop_price"]) if row["stop_price"] is not None else None,
                opened_at=datetime.fromisoformat(row["opened_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                status=row["status"],
                risk_pct=float(row["risk_pct"]),
                metadata=json.loads(row["payload"] or "{}"),
            )
        return result

    def insert_trade(
        self,
        client_order_id: str,
        symbol: str,
        strategy_id: str,
        mode: str,
        side: str,
        entry_price: float,
        exit_price: float,
        qty: float,
        pnl: float,
        fee: float,
        opened_at: datetime,
        closed_at: datetime,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO trades (
                    client_order_id, symbol, strategy_id, mode, side, entry_price, exit_price,
                    qty, pnl, fee, opened_at, closed_at, reason, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_order_id,
                    symbol,
                    strategy_id,
                    mode,
                    side,
                    entry_price,
                    exit_price,
                    qty,
                    pnl,
                    fee,
                    opened_at.isoformat(),
                    closed_at.isoformat(),
                    reason,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )

    def record_equity(
        self,
        mode: str,
        total_equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        drawdown: float,
        note: str = "",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO equity (
                    timestamp, mode, total_equity, realized_pnl, unrealized_pnl, drawdown, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (utc_now(), mode, total_equity, realized_pnl, unrealized_pnl, drawdown, note),
            )

    def log_event(
        self,
        event_type: str,
        message: str,
        mode: str = "system",
        level: str = "INFO",
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    timestamp, mode, event_type, level, message, payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now(),
                    mode,
                    event_type,
                    level,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )

    def get_latest_equity(self, mode: str | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM equity"
        params: tuple[Any, ...] = ()
        if mode:
            query += " WHERE mode = ?"
            params = (mode,)
        query += " ORDER BY id DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_control_state(self) -> dict[str, bool]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type FROM events
                WHERE event_type IN (
                    'system_pause', 'system_resume', 'system_kill', 'system_clear_kill'
                )
                ORDER BY id ASC
                """
            ).fetchall()

        state = {"paused": False, "killed": False}
        for row in rows:
            event_type = row["event_type"]
            if event_type == "system_pause":
                state["paused"] = True
            elif event_type == "system_resume":
                state["paused"] = False
            elif event_type == "system_kill":
                state["killed"] = True
            elif event_type == "system_clear_kill":
                state["killed"] = False
        return state

    def get_trades(self, mode: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM trades"
        params: tuple[Any, ...] = ()
        if mode:
            query += " WHERE mode = ?"
            params = (mode,)
        query += " ORDER BY id ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

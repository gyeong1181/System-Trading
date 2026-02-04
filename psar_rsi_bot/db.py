from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class BotDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path.as_posix())

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    received_at TEXT,
                    payload_json TEXT,
                    status TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_key TEXT PRIMARY KEY,
                    signal_id TEXT,
                    symbol TEXT,
                    action TEXT,
                    side TEXT,
                    qty REAL,
                    request_json TEXT,
                    response_json TEXT,
                    status TEXT,
                    error TEXT,
                    created_at TEXT
                )
                """
            )

    def insert_signal(self, signal_id: str, payload: Dict[str, Any], status: str) -> bool:
        now = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO signals(signal_id, received_at, payload_json, status) VALUES (?, ?, ?, ?)",
                    (signal_id, now, payload_json, status),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_signal_status(self, signal_id: str, status: str):
        with self._connect() as conn:
            conn.execute("UPDATE signals SET status=? WHERE signal_id=?", (status, signal_id))

    def insert_order(
        self,
        order_key: str,
        signal_id: str,
        symbol: str,
        action: str,
        side: str,
        qty: float,
        request: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        status: str,
        error: Optional[str] = None,
    ):
        now = datetime.utcnow().isoformat()
        request_json = json.dumps(request, ensure_ascii=False)
        response_json = json.dumps(response, ensure_ascii=False) if response else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders
                (order_key, signal_id, symbol, action, side, qty, request_json, response_json, status, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_key,
                    signal_id,
                    symbol,
                    action,
                    side,
                    qty,
                    request_json,
                    response_json,
                    status,
                    error,
                    now,
                ),
            )

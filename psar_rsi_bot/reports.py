from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class TradeReporter:
    def __init__(self):
        self.trade_log = REPORTS_DIR / "trade_log.csv"
        self.equity_log = REPORTS_DIR / "equity_curve.csv"
        if not self.trade_log.exists():
            self.trade_log.write_text(
                "timestamp,mode,action,side,qty,price,reason,pnl,equity\n",
                encoding="utf-8",
            )
        if not self.equity_log.exists():
            self.equity_log.write_text("timestamp,mode,equity\n", encoding="utf-8")

    def log_entry(self, mode: str, side: str, qty: float, price: float):
        self._append_trade(
            action="ENTRY",
            mode=mode,
            side=side,
            qty=qty,
            price=price,
            reason="Signal",
            pnl="",
            equity="",
        )

    def log_exit(
        self,
        mode: str,
        side: str,
        qty: float,
        price: float,
        reason: str,
        pnl: float,
        equity: float,
    ):
        self._append_trade(
            action="EXIT",
            mode=mode,
            side=side,
            qty=qty,
            price=price,
            reason=reason,
            pnl=f"{pnl:.2f}",
            equity=f"{equity:.2f}",
        )
        self.log_equity(mode, equity)

    def log_equity(self, mode: str, equity: float):
        with self.equity_log.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([_utc_now(), mode, f"{equity:.2f}"])

    def _append_trade(
        self,
        action: str,
        mode: str,
        side: str,
        qty: float,
        price: float,
        reason: str,
        pnl: str,
        equity: str,
    ):
        with self.trade_log.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    _utc_now(),
                    mode,
                    action,
                    side.upper(),
                    f"{qty:.6f}",
                    f"{price:.2f}",
                    reason,
                    pnl,
                    equity,
                ]
            )

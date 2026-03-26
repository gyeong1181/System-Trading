from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.config import Settings
from src.db import Database
from src.models import PositionState


class RiskManager:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def current_portfolio_risk(self, positions: dict[str, PositionState]) -> float:
        return sum(position.risk_pct for position in positions.values())

    def strategy_disabled(self, strategy_id: str) -> bool:
        trades = [row for row in self.db.get_trades() if row["strategy_id"] == strategy_id]
        if not trades:
            return False
        total_pnl = sum(float(row["pnl"]) for row in trades)
        return (total_pnl / self.settings.starting_equity) <= float(self.settings.risk["strategy_disable_pct"])

    def _pnl_since(self, since: datetime) -> float:
        pnl = 0.0
        for trade in self.db.get_trades():
            closed_at = datetime.fromisoformat(trade["closed_at"])
            if closed_at >= since:
                pnl += float(trade["pnl"])
        return pnl

    def daily_limit_hit(self) -> bool:
        since = datetime.now(UTC) - timedelta(days=1)
        pnl_pct = self._pnl_since(since) / self.settings.starting_equity
        return pnl_pct <= float(self.settings.risk["daily_stop_pct"])

    def weekly_limit_hit(self) -> bool:
        since = datetime.now(UTC) - timedelta(days=7)
        pnl_pct = self._pnl_since(since) / self.settings.starting_equity
        return pnl_pct <= float(self.settings.risk["weekly_stop_pct"])

    def can_trade(self, strategy_id: str, positions: dict[str, PositionState]) -> tuple[bool, str]:
        if self.daily_limit_hit():
            return False, "일일 손실 한도에 도달했습니다."
        if self.weekly_limit_hit():
            return False, "주간 손실 한도에 도달했습니다."
        if self.strategy_disabled(strategy_id):
            return False, "전략 손실 한도를 초과해 비활성화되었습니다."
        remaining = float(self.settings.risk["total_risk_pct"]) - self.current_portfolio_risk(positions)
        if remaining <= 0:
            return False, "포트폴리오 총 리스크 한도를 초과했습니다."
        return True, ""

    def size_order(
        self,
        symbol: str,
        entry_price: float,
        stop_price: float | None,
        equity: float,
        positions: dict[str, PositionState],
    ) -> tuple[float, float]:
        if stop_price is None:
            return 0.0, 0.0
        remaining_total = max(
            0.0,
            float(self.settings.risk["total_risk_pct"]) - self.current_portfolio_risk(positions),
        )
        risk_pct = min(float(self.settings.risk["symbol_risk_pct"]), remaining_total)
        distance = abs(entry_price - stop_price)
        if risk_pct <= 0 or distance <= 0:
            return 0.0, 0.0
        risk_amount = equity * risk_pct
        qty = risk_amount / distance
        qty = round(qty, 3 if symbol.startswith("BTC") else 2)
        return max(qty, 0.0), risk_pct

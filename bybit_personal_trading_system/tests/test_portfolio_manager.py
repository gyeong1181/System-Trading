from __future__ import annotations

from datetime import UTC, datetime

from portfolio.manager import PortfolioManager
from portfolio.risk import RiskManager
from src.config import load_settings
from src.db import Database
from src.models import PositionState, TradeSignal


def test_lower_priority_opposite_signal_is_ignored(repo_root) -> None:
    settings = load_settings(str(repo_root))
    db = Database(settings.database_path)
    db.initialize()
    risk_manager = RiskManager(settings, db)
    manager = PortfolioManager(settings, db, risk_manager)

    db.upsert_position(
        PositionState(
            symbol="ETHUSDT",
            strategy_id="S1",
            mode="demo",
            side="long",
            qty=1.0,
            entry_price=100.0,
            stop_price=95.0,
            opened_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            risk_pct=0.007,
            metadata={},
        )
    )

    orders = manager.approve_signals(
        [
            TradeSignal("S2", "ETHUSDT", "60", "entry", "short", datetime.now(UTC), 99.0, 101.0),
        ],
        mode="demo",
        equity=280.0,
    )
    assert orders == []


def test_higher_priority_signal_reverses_position(repo_root) -> None:
    settings = load_settings(str(repo_root))
    db = Database(settings.database_path)
    db.initialize()
    risk_manager = RiskManager(settings, db)
    manager = PortfolioManager(settings, db, risk_manager)

    db.upsert_position(
        PositionState(
            symbol="ETHUSDT",
            strategy_id="S2",
            mode="demo",
            side="long",
            qty=1.0,
            entry_price=100.0,
            stop_price=95.0,
            opened_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            risk_pct=0.007,
            metadata={},
        )
    )

    orders = manager.approve_signals(
        [
            TradeSignal("S1", "ETHUSDT", "240", "entry", "short", datetime.now(UTC), 99.0, 102.0),
        ],
        mode="demo",
        equity=280.0,
    )
    assert len(orders) == 2
    assert orders[0].action == "close"
    assert orders[1].action == "open"

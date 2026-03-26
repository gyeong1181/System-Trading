from __future__ import annotations

from datetime import UTC, datetime

from portfolio.risk import RiskManager
from src.config import Settings
from src.db import Database
from src.models import ExecutionOrder, PositionState, TradeSignal


class PortfolioManager:
    def __init__(self, settings: Settings, db: Database, risk_manager: RiskManager) -> None:
        self.settings = settings
        self.db = db
        self.risk_manager = risk_manager

    def restore_positions(self, mode: str) -> dict[str, PositionState]:
        return self.db.get_open_positions(mode=mode)

    def approve_signals(self, signals: list[TradeSignal], mode: str, equity: float) -> list[ExecutionOrder]:
        open_positions = self.restore_positions(mode)
        orders: list[ExecutionOrder] = []
        signals_by_symbol: dict[str, list[TradeSignal]] = {}
        for signal in signals:
            signals_by_symbol.setdefault(signal.symbol, []).append(signal)

        for symbol, symbol_signals in signals_by_symbol.items():
            symbol_signals.sort(key=lambda item: self.settings.strategy_configs[item.strategy_id].priority)
            current_position = open_positions.get(symbol)

            if current_position:
                exit_signal = next(
                    (
                        signal
                        for signal in symbol_signals
                        if signal.action == "exit"
                        and signal.strategy_id == current_position.strategy_id
                        and signal.side == current_position.side
                    ),
                    None,
                )
                if exit_signal:
                    orders.append(
                        self._close_order(
                            current_position,
                            reason="전략 청산 신호",
                            signal_time=exit_signal.bar_time,
                        )
                    )
                    del open_positions[symbol]
                    current_position = None

            entries = [signal for signal in symbol_signals if signal.action == "entry"]
            if not entries:
                continue
            chosen = entries[0]
            chosen_priority = self.settings.strategy_configs[chosen.strategy_id].priority

            if current_position:
                current_priority = self.settings.strategy_configs[current_position.strategy_id].priority
                if chosen.side == current_position.side:
                    continue
                if chosen_priority >= current_priority:
                    continue
                orders.append(
                    self._close_order(
                        current_position,
                        reason=f"상위 전략 {chosen.strategy_id} 전환",
                        signal_time=chosen.bar_time,
                    )
                )
                del open_positions[symbol]

            can_trade, reason = self.risk_manager.can_trade(chosen.strategy_id, open_positions)
            if not can_trade:
                self.db.log_event(
                    "risk_block",
                    f"{chosen.strategy_id} {symbol} 진입 차단: {reason}",
                    mode=mode,
                    payload={"symbol": symbol},
                )
                continue

            qty, risk_pct = self.risk_manager.size_order(
                symbol=symbol,
                entry_price=chosen.price,
                stop_price=chosen.stop_price,
                equity=equity,
                positions=open_positions,
            )
            if qty <= 0:
                continue

            order = ExecutionOrder(
                client_order_id=f"{chosen.dedup_key()}-open",
                symbol=chosen.symbol,
                strategy_id=chosen.strategy_id,
                mode=mode,
                action="open",
                side=chosen.side,
                qty=qty,
                reference_price=chosen.price,
                stop_price=chosen.stop_price,
                reason="진입 승인",
                signal_time=chosen.bar_time,
                leverage=self.settings.strategy_configs[chosen.strategy_id].leverage,
                metadata={"risk_pct": risk_pct, "confidence": chosen.confidence, **chosen.metadata},
            )
            orders.append(order)

            open_positions[symbol] = PositionState(
                symbol=order.symbol,
                strategy_id=order.strategy_id,
                mode=order.mode,
                side=order.side,
                qty=order.qty,
                entry_price=order.reference_price,
                stop_price=order.stop_price,
                opened_at=order.signal_time,
                updated_at=datetime.now(UTC),
                risk_pct=risk_pct,
                metadata=order.metadata,
            )
        return orders

    def _close_order(self, position: PositionState, reason: str, signal_time: datetime) -> ExecutionOrder:
        return ExecutionOrder(
            client_order_id=f"{position.strategy_id}-{position.symbol}-{signal_time.strftime('%Y%m%d%H%M%S')}-close",
            symbol=position.symbol,
            strategy_id=position.strategy_id,
            mode=position.mode,
            action="close",
            side=position.side,
            qty=position.qty,
            reference_price=position.entry_price,
            stop_price=position.stop_price,
            reason=reason,
            signal_time=signal_time,
            reduce_only=True,
            leverage=1,
            metadata=position.metadata,
        )

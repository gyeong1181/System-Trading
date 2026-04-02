from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import threading
from typing import Any
from zoneinfo import ZoneInfo

from alerts.telegram import TelegramNotifier
from execution.bybit_client import BybitClient
from portfolio.manager import PortfolioManager
from research.backtest import apply_fill_price
from research.data_manager import MarketDataManager
from src.config import Settings
from src.db import Database
from src.models import ExecutionOrder, PositionState, TradeSignal


class ExecutionEngine:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        notifier: TelegramNotifier,
        data_manager: MarketDataManager,
        portfolio_manager: PortfolioManager,
        strategies: dict[str, object],
        mode: str,
    ) -> None:
        self.settings = settings
        self.db = db
        self.notifier = notifier
        self.data_manager = data_manager
        self.portfolio_manager = portfolio_manager
        self.strategies = strategies
        self.mode = mode
        self.client = BybitClient(settings, mode)
        self.stop_event = threading.Event()
        self.last_daily_key = ""
        self.last_monthly_key = ""

        latest_equity = self.db.get_latest_equity(self.mode)
        if self.mode == "paper" and latest_equity:
            self.paper_realized_equity = float(latest_equity["total_equity"]) - float(latest_equity["unrealized_pnl"])
        else:
            self.paper_realized_equity = float(self.settings.starting_equity)
        peak_equity = self.db.get_peak_equity(self.mode)
        self.paper_peak_equity = peak_equity if peak_equity is not None else max(self.paper_realized_equity, float(self.settings.starting_equity))

    def _load_research_candidates(self) -> set[str]:
        if not self.settings.auto_select_from_research or not self.settings.state_path.exists():
            return set()
        payload = json.loads(self.settings.state_path.read_text(encoding="utf-8"))
        allowed = set()
        for result in payload.get("results", []):
            if self.mode == "live" and result["classification"] == "candidate":
                allowed.add(result["strategy_id"])
            elif self.mode in {"demo", "paper"} and result["classification"] in {"candidate", "shadow"}:
                allowed.add(result["strategy_id"])
        return allowed

    def _rollout_ids(self) -> set[str]:
        if self.mode == "paper":
            return set(self.settings.mode.get("paper_enabled_strategies", self.settings.mode["demo_enabled_strategies"]))
        if self.mode == "demo":
            return set(self.settings.mode["demo_enabled_strategies"])
        if self.settings.live_rollout.upper() == "S1_S2":
            return {"S1", "S2"}
        return {"S1"}

    def _active_strategies(self) -> dict[str, object]:
        rollout = self._rollout_ids()
        candidates = self._load_research_candidates()
        active: dict[str, object] = {}
        for strategy_id, strategy in self.strategies.items():
            if strategy_id not in rollout:
                continue
            if self.mode == "live" and strategy.config.demo_only:
                continue
            if candidates and strategy_id not in candidates:
                continue
            active[strategy_id] = strategy
        if not active:
            for strategy_id, strategy in self.strategies.items():
                if strategy_id in rollout and not (self.mode == "live" and strategy.config.demo_only):
                    active[strategy_id] = strategy
        return active

    def _subscriptions(self, active: dict[str, object]) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        subscriptions: list[dict[str, str]] = []
        for strategy in active.values():
            for symbol in strategy.config.symbols:
                key = (symbol, strategy.config.timeframe)
                if key in seen:
                    continue
                seen.add(key)
                subscriptions.append({"symbol": symbol, "interval": strategy.config.timeframe})
        return subscriptions

    def _latest_equity(self) -> float:
        latest = self.db.get_latest_equity(self.mode)
        if latest:
            return float(latest["total_equity"])
        return float(self.settings.starting_equity)

    def _current_equity_for_sizing(self) -> float:
        if self.mode == "paper":
            return self._paper_total_equity()
        return self.client.fetch_wallet_equity(self._latest_equity())

    def _status_message(self) -> str:
        positions = self.db.get_open_positions(self.mode)
        return (
            f"{self.mode.upper()} 상태\n"
            f"열린 포지션 {len(positions)}개\n"
            f"최근 총자산 {self._latest_equity():.2f} USDT"
        )

    def _handle_command(self, command: str) -> str:
        if command == "/status":
            return self._status_message()
        if command == "/pause":
            self.db.log_event("system_pause", "텔레그램에서 일시 중지를 요청했습니다.")
            return "신규 진입을 일시 중지했습니다."
        if command == "/resume":
            self.db.log_event("system_clear_kill", "텔레그램에서 킬 스위치를 해제했습니다.")
            self.db.log_event("system_resume", "텔레그램에서 재개를 요청했습니다.")
            return "시스템을 재개했습니다."
        if command == "/kill":
            self.db.log_event("system_kill", "텔레그램에서 킬 스위치를 요청했습니다.")
            return "킬 스위치를 켰습니다. 포지션 정리 후 종료합니다."
        return ""

    def _summary_stats(self, start_key: str, monthly: bool = False) -> tuple[float, int, float]:
        trades = self.db.get_trades(self.mode)
        pnl = 0.0
        selected = []
        for trade in trades:
            closed_at = datetime.fromisoformat(trade["closed_at"])
            key = closed_at.strftime("%Y-%m" if monthly else "%Y-%m-%d")
            if key == start_key:
                pnl += float(trade["pnl"])
                selected.append(trade)
        win_rate = 0.0
        if selected:
            win_rate = sum(1 for trade in selected if float(trade["pnl"]) > 0) / len(selected)
        return pnl, len(selected), win_rate

    def _maybe_send_summaries(self) -> None:
        now = datetime.now(ZoneInfo(self.settings.timezone))
        daily_key = now.strftime("%Y-%m-%d")
        monthly_key = now.strftime("%Y-%m")
        summary_hour = int(self.settings.execution["summary_hour_kr"])
        if now.hour == summary_hour and self.last_daily_key != daily_key:
            pnl, trades, win_rate = self._summary_stats(daily_key)
            self.notifier.send_daily_summary(pnl, trades, win_rate)
            self.last_daily_key = daily_key
        if now.day == 1 and now.hour == summary_hour and self.last_monthly_key != monthly_key:
            previous_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            pnl, trades, win_rate = self._summary_stats(previous_month, monthly=True)
            self.notifier.send_monthly_summary(pnl, trades, win_rate)
            self.last_monthly_key = monthly_key

    def _reconcile_positions(self) -> None:
        if self.mode == "paper":
            return
        db_positions = self.db.get_open_positions(self.mode)
        exchange_positions = {row["symbol"]: row for row in self.client.fetch_open_positions()}
        for symbol in db_positions:
            if symbol not in exchange_positions:
                self.db.close_position(symbol)
                self.db.log_event("reconcile_close", f"{symbol} DB 포지션을 종료 상태로 정리했습니다.", mode=self.mode)
        for symbol, exchange_position in exchange_positions.items():
            if symbol in db_positions:
                continue
            recovered = PositionState(
                symbol=symbol,
                strategy_id="recovered",
                mode=self.mode,
                side=exchange_position["side"],
                qty=exchange_position["qty"],
                entry_price=exchange_position["entry_price"],
                stop_price=None,
                opened_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                risk_pct=0.0,
                metadata={"recovered": True},
            )
            self.db.upsert_position(recovered)
            self.db.log_event("reconcile_recover", f"{symbol} 거래소 포지션을 복구했습니다.", mode=self.mode)

    def _paper_total_equity(self, mark_prices: dict[str, float] | None = None) -> float:
        mark_prices = mark_prices or {}
        unrealized = 0.0
        for position in self.db.get_open_positions(self.mode).values():
            mark_price = float(mark_prices.get(position.symbol, position.entry_price))
            if position.side == "long":
                unrealized += (mark_price - position.entry_price) * position.qty
            else:
                unrealized += (position.entry_price - mark_price) * position.qty
        return self.paper_realized_equity + unrealized

    def _record_paper_equity(self, mark_prices: dict[str, float] | None = None, note: str = "") -> None:
        mark_prices = mark_prices or {}
        unrealized = 0.0
        for position in self.db.get_open_positions(self.mode).values():
            mark_price = float(mark_prices.get(position.symbol, position.entry_price))
            if position.side == "long":
                unrealized += (mark_price - position.entry_price) * position.qty
            else:
                unrealized += (position.entry_price - mark_price) * position.qty
        total_equity = self.paper_realized_equity + unrealized
        self.paper_peak_equity = max(self.paper_peak_equity, total_equity)
        drawdown = 0.0
        if self.paper_peak_equity > 0:
            drawdown = (total_equity / self.paper_peak_equity) - 1.0
        realized_pnl = self.paper_realized_equity - float(self.settings.starting_equity)
        self.db.record_equity(self.mode, total_equity, realized_pnl, unrealized, drawdown, note=note)

    def _execute_paper_order(self, order: ExecutionOrder, position_before: PositionState | None) -> None:
        fee_rate = float(self.settings.execution["fee_rate"])
        raw: dict[str, Any] = {"mode": "paper", "reference_price": order.reference_price}

        if order.action == "open":
            executed_price = apply_fill_price(order.reference_price, order.side, float(self.settings.execution["slippage"]), is_entry=True)
            entry_fee = executed_price * order.qty * fee_rate
            self.paper_realized_equity -= entry_fee
            metadata = {**order.metadata, "entry_fee": entry_fee, "paper_fill_price": executed_price}
            position = PositionState(
                symbol=order.symbol,
                strategy_id=order.strategy_id,
                mode=order.mode,
                side=order.side,
                qty=order.qty,
                entry_price=executed_price,
                stop_price=order.stop_price,
                opened_at=order.signal_time,
                updated_at=datetime.now(UTC),
                risk_pct=float(order.metadata.get("risk_pct", 0.0)),
                metadata=metadata,
            )
            self.db.insert_order(order, status="filled", exchange_order_id=f"paper-{order.client_order_id}", payload=raw)
            self.db.upsert_position(position)
            self.notifier.send_trade_alert(order, "가상 체결")
            self._record_paper_equity({order.symbol: executed_price}, note=order.reason)
            return

        if order.action == "close" and position_before is not None:
            executed_price = apply_fill_price(order.reference_price, order.side, float(self.settings.execution["slippage"]), is_entry=False)
            entry_fee = float(position_before.metadata.get("entry_fee", 0.0))
            close_fee = executed_price * order.qty * fee_rate
            gross_pnl = (
                (executed_price - position_before.entry_price) * order.qty
                if position_before.side == "long"
                else (position_before.entry_price - executed_price) * order.qty
            )
            self.paper_realized_equity += gross_pnl - close_fee
            total_fee = entry_fee + close_fee
            total_pnl = gross_pnl - total_fee
            self.db.insert_order(order, status="filled", exchange_order_id=f"paper-{order.client_order_id}", payload=raw)
            self.db.close_position(order.symbol)
            self.db.insert_trade(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                strategy_id=position_before.strategy_id,
                mode=self.mode,
                side=position_before.side,
                entry_price=position_before.entry_price,
                exit_price=executed_price,
                qty=order.qty,
                pnl=total_pnl,
                fee=total_fee,
                opened_at=position_before.opened_at,
                closed_at=datetime.now(UTC),
                reason=order.reason,
                payload={"metadata": order.metadata, "paper": True},
            )
            self.notifier.send_trade_alert(order, "가상 청산", pnl=total_pnl)
            self._record_paper_equity({order.symbol: executed_price}, note=order.reason)

    def _execute_order(self, order: ExecutionOrder) -> None:
        if self.db.has_order(order.client_order_id):
            return

        position_before = self.db.get_open_positions(self.mode).get(order.symbol)
        if self.mode == "paper":
            self._execute_paper_order(order, position_before)
            return

        result = self.client.place_order(order)
        self.db.insert_order(order, status="submitted", exchange_order_id=result["order_id"], payload=result["raw"])

        executed_price = float(result.get("avg_price") or order.reference_price)
        if order.action == "open":
            position = PositionState(
                symbol=order.symbol,
                strategy_id=order.strategy_id,
                mode=order.mode,
                side=order.side,
                qty=order.qty,
                entry_price=executed_price,
                stop_price=order.stop_price,
                opened_at=order.signal_time,
                updated_at=datetime.now(UTC),
                risk_pct=float(order.metadata.get("risk_pct", 0.0)),
                metadata=order.metadata,
            )
            self.db.upsert_position(position)
            self.notifier.send_trade_alert(order, "체결")
        elif order.action == "close" and position_before is not None:
            self.db.close_position(order.symbol)
            if position_before.side == "long":
                pnl = (executed_price - position_before.entry_price) * order.qty
            else:
                pnl = (position_before.entry_price - executed_price) * order.qty
            fee = (position_before.entry_price + executed_price) * order.qty * float(self.settings.execution["fee_rate"])
            pnl -= fee
            self.db.insert_trade(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                strategy_id=position_before.strategy_id,
                mode=self.mode,
                side=position_before.side,
                entry_price=position_before.entry_price,
                exit_price=executed_price,
                qty=order.qty,
                pnl=pnl,
                fee=fee,
                opened_at=position_before.opened_at,
                closed_at=datetime.now(UTC),
                reason=order.reason,
                payload={"metadata": order.metadata},
            )
            self.notifier.send_trade_alert(order, "청산", pnl=pnl)

        equity = self.client.fetch_wallet_equity(self._latest_equity())
        self.db.record_equity(self.mode, equity, 0.0, 0.0, 0.0, note=order.reason)

    def _process_bar(self, symbol: str, interval: str, timestamp_ms: int) -> None:
        state = self.db.get_control_state()
        if state["killed"]:
            positions = self.db.get_open_positions(self.mode)
            for position in positions.values():
                close_order = ExecutionOrder(
                    client_order_id=f"kill-{position.symbol}-{timestamp_ms}",
                    symbol=position.symbol,
                    strategy_id=position.strategy_id,
                    mode=self.mode,
                    action="close",
                    side=position.side,
                    qty=position.qty,
                    reference_price=position.entry_price,
                    stop_price=position.stop_price,
                    reason="킬 스위치 청산",
                    signal_time=datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC),
                    reduce_only=True,
                    leverage=1,
                    metadata=position.metadata,
                )
                self._execute_order(close_order)
            self.notifier.send_message(f"{self.mode.upper()} 엔진을 킬 스위치로 종료합니다.")
            self.stop_event.set()
            return

        bundle = self.data_manager.update_market_data(symbol, interval)
        frame = bundle["frame"].tail(int(self.settings.execution["bar_limit"]))
        active = self._active_strategies()
        signals: list[TradeSignal] = []
        for strategy in active.values():
            if symbol not in strategy.config.symbols or strategy.config.timeframe != interval:
                continue
            signal = strategy.latest_signal(frame)
            if signal is not None:
                signals.append(signal)

        if state["paused"]:
            signals = [signal for signal in signals if signal.action == "exit"]

        last_close = float(frame["close"].iloc[-1])
        if not signals:
            if self.mode == "paper":
                self._record_paper_equity({symbol: last_close}, note="bar_close")
            self._maybe_send_summaries()
            return

        equity = self._current_equity_for_sizing()
        orders = self.portfolio_manager.approve_signals(signals=signals, mode=self.mode, equity=equity)
        for order in orders:
            self._execute_order(order)
        if self.mode == "paper":
            self._record_paper_equity({symbol: last_close}, note="bar_close")
        self._maybe_send_summaries()

    def run(self) -> None:
        control = self.db.get_control_state()
        if control["killed"]:
            raise RuntimeError("킬 스위치가 켜진 상태입니다. `make resume` 또는 `/resume`으로 해제하세요.")

        self._reconcile_positions()
        active = self._active_strategies()
        subscriptions = self._subscriptions(active)
        self.db.log_event("engine_start", f"{self.mode} 엔진을 시작합니다.", mode=self.mode)
        self.notifier.send_message(f"{self.mode.upper()} 엔진을 시작합니다.")

        command_thread = threading.Thread(
            target=self.notifier.poll_commands,
            args=(self.stop_event, self._handle_command),
            daemon=True,
        )
        command_thread.start()

        self.client.start_kline_stream(subscriptions, self._process_bar, self.stop_event, notifier=self.notifier)

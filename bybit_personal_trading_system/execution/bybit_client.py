from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_DOWN
import time
from typing import Any

from src.config import Settings
from src.models import ExecutionOrder


class BybitClient:
    def __init__(self, settings: Settings, mode: str) -> None:
        self.settings = settings
        self.mode = mode
        self._http = None
        self._instrument_steps: dict[str, str] = {}

    @property
    def testnet(self) -> bool:
        if self.mode == "demo":
            return bool(self.settings.execution["demo_testnet"])
        return False

    def _ensure_http(self):
        if self._http is not None:
            return self._http
        try:
            from pybit.unified_trading import HTTP
        except ImportError as exc:
            raise RuntimeError("pybit가 설치되지 않았습니다. `pip install -r requirements.txt`를 먼저 실행하세요.") from exc
        self._http = HTTP(
            testnet=self.testnet,
            api_key=self.settings.bybit_api_key,
            api_secret=self.settings.bybit_api_secret,
        )
        return self._http

    def ensure_symbol_mode(self, symbol: str, leverage: int) -> None:
        session = self._ensure_http()
        try:
            session.switch_position_mode(category="linear", symbol=symbol, mode=0)
        except Exception:
            pass
        try:
            session.switch_margin_mode(category="linear", symbol=symbol, tradeMode=1, buyLeverage=str(leverage), sellLeverage=str(leverage))
        except Exception:
            pass
        try:
            session.set_leverage(category="linear", symbol=symbol, buyLeverage=str(leverage), sellLeverage=str(leverage))
        except Exception:
            pass

    def _get_qty_step(self, symbol: str) -> str:
        if symbol in self._instrument_steps:
            return self._instrument_steps[symbol]
        session = self._ensure_http()
        response = session.get_instruments_info(category="linear", symbol=symbol)
        items = response.get("result", {}).get("list", [])
        if not items:
            step = "0.001"
        else:
            step = items[0].get("lotSizeFilter", {}).get("qtyStep", "0.001")
        self._instrument_steps[symbol] = step
        return step

    def round_qty(self, symbol: str, qty: float) -> str:
        step = Decimal(self._get_qty_step(symbol))
        rounded = Decimal(str(qty)).quantize(step, rounding=ROUND_DOWN)
        return format(rounded, "f")

    def fetch_wallet_equity(self, fallback: float) -> float:
        session = self._ensure_http()
        try:
            response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            rows = response.get("result", {}).get("list", [])
            if not rows:
                return fallback
            total_equity = rows[0].get("totalEquity")
            return float(total_equity) if total_equity is not None else fallback
        except Exception:
            return fallback

    def fetch_open_positions(self) -> list[dict[str, Any]]:
        session = self._ensure_http()
        try:
            response = session.get_positions(category="linear", settleCoin="USDT")
        except Exception:
            return []
        items = response.get("result", {}).get("list", [])
        results = []
        for item in items:
            size = float(item.get("size") or 0.0)
            if size <= 0:
                continue
            side = "long" if item.get("side") == "Buy" else "short"
            results.append(
                {
                    "symbol": item.get("symbol"),
                    "side": side,
                    "qty": size,
                    "entry_price": float(item.get("avgPrice") or 0.0),
                }
            )
        return results

    def place_order(self, order: ExecutionOrder) -> dict[str, Any]:
        session = self._ensure_http()
        self.ensure_symbol_mode(order.symbol, order.leverage)
        side = "Buy" if (order.action == "open" and order.side == "long") or (order.action == "close" and order.side == "short") else "Sell"
        params: dict[str, Any] = {
            "category": "linear",
            "symbol": order.symbol,
            "side": side,
            "orderType": "Market",
            "qty": self.round_qty(order.symbol, order.qty),
            "reduceOnly": order.reduce_only,
            "positionIdx": 0,
            "orderLinkId": order.client_order_id,
        }
        if order.action == "open" and order.stop_price is not None:
            params["tpslMode"] = "Full"
            params["stopLoss"] = str(order.stop_price)
            params["slOrderType"] = "Market"
        response = session.place_order(**params)
        result = response.get("result", {})
        return {
            "order_id": result.get("orderId", ""),
            "avg_price": order.reference_price,
            "raw": response,
        }

    def close_all_positions(self) -> None:
        for position in self.fetch_open_positions():
            order = ExecutionOrder(
                client_order_id=f"kill-{position['symbol']}-{int(time.time())}",
                symbol=position["symbol"],
                strategy_id="system",
                mode=self.mode,
                action="close",
                side=position["side"],
                qty=position["qty"],
                reference_price=position["entry_price"],
                stop_price=None,
                reason="킬 스위치",
                signal_time=datetime.now(UTC),
                reduce_only=True,
                leverage=1,
            )
            self.place_order(order)

    def start_kline_stream(self, subscriptions: list[dict[str, str]], on_bar_close, stop_event, notifier=None) -> None:
        if not subscriptions:
            raise RuntimeError("구독할 심볼이 없습니다. 리서치 결과 또는 설정을 확인하세요.")
        try:
            from pybit.unified_trading import WebSocket
        except ImportError as exc:
            raise RuntimeError("pybit가 설치되지 않았습니다. `pip install -r requirements.txt`를 먼저 실행하세요.") from exc

        while not stop_event.is_set():
            ws = None
            try:
                ws = WebSocket(testnet=self.testnet, channel_type="linear")

                def callback(message: dict[str, Any]) -> None:
                    rows = message.get("data", [])
                    if isinstance(rows, dict):
                        rows = [rows]
                    for row in rows:
                        confirmed = row.get("confirm")
                        if not confirmed:
                            continue
                        symbol = str(row.get("symbol"))
                        interval = str(row.get("interval"))
                        timestamp_ms = int(row.get("start") or row.get("startTime") or row.get("timestamp"))
                        on_bar_close(symbol, interval, timestamp_ms)

                for sub in subscriptions:
                    ws.kline_stream(interval=int(sub["interval"]), symbol=sub["symbol"], callback=callback)

                while not stop_event.is_set():
                    time.sleep(1)
            except Exception as exc:
                if notifier is not None:
                    notifier.send_error_alert(f"웹소켓 연결이 끊어졌습니다. {self.settings.execution['reconnect_seconds']}초 뒤 재연결합니다. 상세: {exc}")
                time.sleep(int(self.settings.execution["reconnect_seconds"]))
            finally:
                if ws is not None:
                    try:
                        ws.exit()
                    except Exception:
                        pass

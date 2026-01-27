from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None

try:
    import websockets  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    websockets = None

from utils import Candle, get_logger
from reports import TradeReporter


OrderHandler = Callable[[Candle], Awaitable[None]]


@dataclass
class Position:
    side: str
    qty: float
    entry_price: float
    stop_price: float
    tp1_price: float
    runner_price: float
    trail_offset: float
    filled_tp1: bool = False
    highest: float = field(default=0.0)
    lowest: float = field(default=0.0)
    initial_qty: float = field(default=0.0)

    def __post_init__(self):
        self.highest = self.entry_price
        self.lowest = self.entry_price

    def update_extremes(self, high: float, low: float):
        self.highest = max(self.highest, high)
        self.lowest = min(self.lowest, low)


class ExchangeClient:
    async def fetch_equity(self) -> float:
        raise NotImplementedError

    async def fetch_available_balance(self) -> float:
        raise NotImplementedError

    async def enter_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        tp1_price: float,
        runner_price: float,
        trail_offset: float,
        entry_price: float,
    ) -> Position:
        raise NotImplementedError

    async def close_position(self, symbol: str, qty: Optional[float], price: float, reason: str) -> None:
        raise NotImplementedError

    def get_position(self, symbol: str) -> Optional[Position]:
        raise NotImplementedError

    @property
    def position(self) -> Optional[Position]:
        raise NotImplementedError


class PaperExchangeClient(ExchangeClient):
    def __init__(
        self,
        starting_equity: float = 10000.0,
        fee_rate: float = 0.0005,
        reporter: Optional[TradeReporter] = None,
        notifier=None,
    ):
        self._equity = starting_equity
        self.fee_rate = fee_rate
        self._positions: Dict[str, Position] = {}
        self.logger = get_logger("PaperExchange")
        self.reporter = reporter
        self.notifier = notifier
        self.mode_name = "PAPER"

    async def fetch_equity(self) -> float:
        return self._equity

    async def fetch_available_balance(self) -> float:
        return self._equity

    @property
    def position(self) -> Optional[Position]:
        if self._positions:
            return next(iter(self._positions.values()))
        return None

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol.upper())

    async def enter_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        tp1_price: float,
        runner_price: float,
        trail_offset: float,
        entry_price: float,
    ) -> Position:
        if self._positions.get(symbol.upper()) is not None:
            raise RuntimeError("Position already open")
        self.logger.info(
            "[PAPER] Enter %s %s qty=%.6f entry=%.2f stop=%.2f tp1=%.2f runner=%.2f",
            symbol,
            side.upper(),
            qty,
            entry_price,
            stop_price,
            tp1_price,
            runner_price,
        )
        position = Position(
            side=side,
            qty=qty,
            entry_price=entry_price,
            stop_price=stop_price,
            tp1_price=tp1_price,
            runner_price=runner_price,
            trail_offset=trail_offset,
            initial_qty=qty,
        )
        self._positions[symbol.upper()] = position
        if self.reporter:
            self.reporter.log_entry(self.mode_name, side, qty, entry_price)
        if self.notifier:
            self.notifier.notify_entry(symbol, side, qty, entry_price, self.mode_name)
        return position

    async def close_position(self, symbol: str, qty: Optional[float], price: float, reason: str) -> None:
        position = self._positions.get(symbol.upper())
        if position is None:
            return
        qty_to_close = qty if qty is not None else position.qty
        qty_to_close = min(qty_to_close, position.qty)
        if qty_to_close <= 0:
            return

        direction = 1 if position.side == "long" else -1
        pnl = (price - position.entry_price) * qty_to_close * direction
        fee = price * qty_to_close * self.fee_rate
        self._equity += pnl - fee
        position.qty -= qty_to_close
        self.logger.info(
            "[PAPER] Close %s %s qty=%.6f price=%.2f reason=%s pnl=%.2f equity=%.2f",
            symbol,
            position.side.upper(),
            qty_to_close,
            price,
            reason,
            pnl,
            self._equity,
        )
        if self.reporter:
            self.reporter.log_exit(
                mode=self.mode_name,
                side=position.side,
                qty=qty_to_close,
                price=price,
                reason=reason,
                pnl=pnl,
                equity=self._equity,
            )
        if self.notifier:
            self.notifier.notify_exit(symbol, position.side, qty_to_close, price, pnl, reason, self.mode_name)
        if position.qty <= 1e-8:
            self._positions.pop(symbol.upper(), None)


class BinanceLiveExchange(ExchangeClient):
    BASE_URL = "https://fapi.binance.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        reporter: Optional[TradeReporter] = None,
        fee_rate: float = 0.0005,
        notifier=None,
    ):
        if httpx is None:
            raise RuntimeError("httpx is required for live trading")
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.reporter = reporter
        self.notifier = notifier
        self.logger = get_logger("BinanceLive")
        self._positions: Dict[str, Position] = {}
        self.fee_rate = fee_rate
        self._session = httpx.AsyncClient(base_url=self.BASE_URL, timeout=15)
        self.mode_name = "LIVE"
        self._equity_cache: float = 0.0

    async def close(self):
        await self._session.aclose()

    async def fetch_equity(self) -> float:
        params: Dict[str, str] = {}
        data = await self._signed_request("GET", "/fapi/v2/balance", params)
        usdt = next((item for item in data if item.get("asset") == "USDT"), None)
        if usdt:
            self._equity_cache = float(usdt.get("balance", 0.0))
        if self.reporter and self._equity_cache:
            self.reporter.log_equity(self.mode_name, self._equity_cache)
        return self._equity_cache

    async def fetch_available_balance(self) -> float:
        params: Dict[str, str] = {}
        data = await self._signed_request("GET", "/fapi/v2/balance", params)
        usdt = next((item for item in data if item.get("asset") == "USDT"), None)
        if usdt:
            return float(usdt.get("availableBalance", usdt.get("balance", 0.0)))
        return 0.0

    @property
    def position(self) -> Optional[Position]:
        if self._positions:
            return next(iter(self._positions.values()))
        return None

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol.upper())

    async def enter_position(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        tp1_price: float,
        runner_price: float,
        trail_offset: float,
        entry_price: float,
    ) -> Position:
        await self._place_market_order(symbol, "BUY" if side == "long" else "SELL", qty, reduce_only=False)
        self.logger.info("[LIVE] Entered %s %s qty=%.6f price=%.2f", symbol, side.upper(), qty, entry_price)
        position = Position(
            side=side,
            qty=qty,
            entry_price=entry_price,
            stop_price=stop_price,
            tp1_price=tp1_price,
            runner_price=runner_price,
            trail_offset=trail_offset,
            initial_qty=qty,
        )
        self._positions[symbol.upper()] = position
        if self.reporter:
            self.reporter.log_entry(self.mode_name, side, qty, entry_price)
        if self.notifier:
            self.notifier.notify_entry(symbol, side, qty, entry_price, self.mode_name)
        return position

    async def close_position(self, symbol: str, qty: Optional[float], price: float, reason: str) -> None:
        position = self._positions.get(symbol.upper())
        if position is None:
            return
        qty_to_close = qty if qty is not None else position.qty
        qty_to_close = min(qty_to_close, position.qty)
        if qty_to_close <= 0:
            return
        direction = "SELL" if position.side == "long" else "BUY"
        await self._place_market_order(symbol, direction, qty_to_close, reduce_only=True)
        position.qty -= qty_to_close
        pnl = (price - position.entry_price) * qty_to_close * (1 if position.side == "long" else -1)
        fee = abs(price) * qty_to_close * self.fee_rate
        self._equity_cache += pnl - fee
        self.logger.info(
            "[LIVE] Close %s %s qty=%.6f price=%.2f reason=%s pnl=%.2f",
            symbol,
            position.side.upper(),
            qty_to_close,
            price,
            reason,
            pnl,
        )
        if self.reporter:
            self.reporter.log_exit(
                mode=self.mode_name,
                side=position.side,
                qty=qty_to_close,
                price=price,
                reason=reason,
                pnl=pnl,
                equity=self._equity_cache,
            )
        if self.notifier:
            self.notifier.notify_exit(symbol, position.side, qty_to_close, price, pnl, reason, self.mode_name)
        if position.qty <= 1e-8:
            self._positions.pop(symbol.upper(), None)

    async def _place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool):
        params = {
            "symbol": symbol.upper(),
            "side": side,
            "type": "MARKET",
            "quantity": f"{qty:.6f}",
            "reduceOnly": "true" if reduce_only else "false",
        }
        await self._signed_request("POST", "/fapi/v1/order", params)

    async def _signed_request(self, method: str, path: str, params: Dict[str, str]):
        if "timestamp" not in params:
            params["timestamp"] = str(int(time.time() * 1000))
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, query.encode(), hashlib.sha256).hexdigest()
        query += f"&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        url = f"{path}?{query}"
        max_retries = 5
        base_delay = 60.0
        attempt = 0
        while True:
            try:
                response = await self._session.request(method, url, headers=headers)
            except Exception as exc:
                attempt += 1
                if attempt > max_retries:
                    self.logger.error("Network error after retries: %s", exc)
                    raise
                self.logger.warning("Network error: %s. Retrying in %.0fs", exc, base_delay)
                await asyncio.sleep(base_delay)
                continue

            if response.status_code >= 500:
                attempt += 1
                if attempt > max_retries:
                    self.logger.error("Server error %s: %s", response.status_code, response.text)
                    response.raise_for_status()
                self.logger.warning("Server error %s. Retrying in %.0fs", response.status_code, base_delay)
                await asyncio.sleep(base_delay)
                continue

            if response.status_code >= 400:
                self.logger.error("Binance error %s: %s", response.status_code, response.text)
                response.raise_for_status()
            return response.json()


class BinanceCandleStream:
    def __init__(self, symbol: str, interval: str = "4h", logger: Optional[logging.Logger] = None):
        self.symbol = symbol.lower()
        self.interval = interval
        self.url = f"wss://fstream.binance.com/ws/{self.symbol}@kline_{interval}"
        self.logger = logger or get_logger("BinanceStream")
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self, handler: OrderHandler):
        if websockets is None:
            raise RuntimeError("websockets package not installed. Install websockets to enable live mode.")
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.url, ping_interval=15, ping_timeout=15) as ws:
                    self.logger.info("Connected to Binance %s stream", self.symbol)
                    async for message in ws:
                        if self._stop_event.is_set():
                            break
                        self.logger.debug("Stream message received: %s...", message[:100])
                        payload = json.loads(message)
                        self.logger.debug("Message type: %s", payload.get("e", "unknown"))
                        if payload.get("e") == "kline":
                            kline = payload.get("k", {})
                            if kline.get("x"):
                                self.logger.info(
                                    "KLINE %s %s: close=%s closed=%s t=%s",
                                    kline.get("s"),
                                    kline.get("i"),
                                    kline.get("c"),
                                    kline.get("x"),
                                    kline.get("t"),
                                )
                        candle = Candle.from_binance_ws(payload)
                        if candle.closed:
                            self.logger.info(
                                "Invoking handler for candle at %s closed=%s",
                                candle.timestamp,
                                candle.closed,
                            )
                            await handler(candle)
                            self.logger.info("Handler completed")
            except Exception as exc:
                self.logger.warning("Stream error %s. Reconnecting...", exc)
                await asyncio.sleep(3)

    async def stop(self):
        self._stop_event.set()
        if self._task:
            self._task.cancel()


class BinanceRestClient:
    def __init__(self):
        self.logger = get_logger("BinanceREST")

    async def fetch_klines(self, symbol: str, interval: str = "4h", limit: int = 1500) -> List[Dict[str, float]]:
        params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        base_url = "https://fapi.binance.com/fapi/v1/klines"
        if httpx is not None:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
                klines = resp.json()
        else:  # pragma: no cover - fallback path
            url = f"{base_url}?{urllib.parse.urlencode(params)}"
            loop = asyncio.get_running_loop()

            def _blocking_request():
                with urllib.request.urlopen(url, timeout=15) as response:
                    return json.loads(response.read().decode("utf-8"))

            klines = await loop.run_in_executor(None, _blocking_request)
        candles: List[Dict[str, float]] = []
        for raw in klines:
            candles.append(
                {
                    "timestamp": int(raw[0]),
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                }
            )
        return candles

    async def fetch_exchange_info(self) -> Dict[str, Any]:
        base_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        if httpx is not None:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url)
                resp.raise_for_status()
                return resp.json()
        url = base_url
        loop = asyncio.get_running_loop()

        def _blocking_request():
            with urllib.request.urlopen(url, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))

        return await loop.run_in_executor(None, _blocking_request)

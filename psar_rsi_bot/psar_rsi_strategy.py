from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sqlite3
import time
import math
import urllib.parse
import urllib.request
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import websocket

from exchange import (
    BinanceCandleStream,
    BinanceLiveExchange,
    BinanceRestClient,
    ExchangeClient,
    PaperExchangeClient,
)
from indicators_fixed import compute_psar_rsi_ema
from reports import TradeReporter
from utils import Candle, get_logger, load_env, get_app_logger
from risk_manager import RiskManager, parse_max_notional_map


class BinanceWebSocket:
    def __init__(self, symbol):
        self.symbol = symbol
        self.ws = None
        self.reconnect_interval = 60

    def on_message(self, ws, message):
        """Websocket kline processing with verbose logging."""
        try:
            import json
            msg = json.loads(message)
            print(f"MSG {msg.get('e', 'unknown')}: {msg.get('s', 'N/A')}")

            if msg.get("e") == "kline" and msg["k"]["s"] == "BTCUSDT":
                kline = msg["k"]
                timestamp = kline["t"] // 1000
                close_price = float(kline["c"])
                is_closed = kline["x"]

                print(f"KLINE 1h close: {close_price:.2f}, closed: {is_closed}, t: {timestamp}")

                if is_closed:
                    print("Signal check start...")
                    # TODO: connect existing signal logic here
        except json.JSONDecodeError as exc:
            print(f"JSON error: {exc}")
            print(f"Raw: {message[:100]}...")
        except Exception as exc:
            print(f"on_message exception: {exc}")

    def connect(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    f"wss://stream.binance.com:9443/ws/{self.symbol.lower()}@kline_1h",
                    on_message=self.on_message,
                )
                self.ws.run_forever(ping_interval=60, ping_timeout=10)
            except Exception as exc:
                print(f"WebSocket error: {exc}. Reconnecting in 60s...")
                time.sleep(self.reconnect_interval)


def log_trade_signal(signal_type, symbol, price, psar, rsi, balance=0):
    """CSV analysis log with console output."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{signal_type} {symbol} @ {price:.2f} PSAR:{psar:.4f} RSI:{rsi:.1f}")
    csv_row = [timestamp, symbol, signal_type, price, psar, rsi, balance]
    with open("trade_signals.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_row)


def init_trade_log():
    """Initialize CSV header once."""
    if not os.path.exists("trade_signals.csv"):
        with open("trade_signals.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "symbol", "signal", "price", "psar", "rsi", "balance"])


def send_telegram_message(env: dict, message: str) -> None:
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram notify skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
        with urllib.request.urlopen(url, data=data, timeout=10) as _:
            pass
    except Exception as exc:
        print(f"Telegram notify error: {exc}")


class TelegramNotifier:
    def __init__(self, env: dict):
        self.env = env

    def notify_entry(self, symbol: str, side: str, qty: float, price: float, mode: str):
        send_telegram_message(
            self.env,
            f"[{mode}] ENTRY {symbol} {side.upper()} qty={qty:.6f} price={price:.2f}",
        )

    def notify_exit(self, symbol: str, side: str, qty: float, price: float, pnl: float, reason: str, mode: str):
        send_telegram_message(
            self.env,
            f"[{mode}] EXIT {symbol} {side.upper()} qty={qty:.6f} price={price:.2f}\n"
            f"pnl={pnl:.2f} reason={reason}",
        )


def init_sqlite(db_path: str = "trading_data.db") -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                qty REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                signal TEXT NOT NULL
            )
            """
        )
        conn.commit()


def log_trade_db(
    db_path: str,
    timestamp: str,
    symbol: str,
    side: str,
    price: float,
    qty: float,
    pnl_pct: float,
    signal: str,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trades (timestamp, symbol, side, price, qty, pnl_pct, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, symbol, side, price, qty, pnl_pct, signal),
        )
        conn.commit()


@dataclass
class PsarRsiConfig:
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    ema_length: int = 200
    rsi_length: int = 14
    psar_step: float = 0.02
    psar_max_step: float = 0.2
    risk_pct: float = 1.0  # percent of equity risked per trade
    risk_reward: float = 2.0
    swing_lookback: int = 5
    leverage: float = 1.0
    max_bars: int = 2000
    exit_on_psar_flip: bool = True
    use_heikin_ashi: bool = True


class PsarRsiTrader:
    """
    트레이딩뷰식 파라볼릭 SAR + EMA200 + RSI(50) 전략.
    진입 조건(마감봉 기준):
      - 롱: PSAR가 상승 전환 AND 종가 > EMA200 AND RSI > 50
      - 숏: PSAR가 하락 전환 AND 종가 < EMA200 AND RSI < 50
    리스크: 최근 스윙 고점/저점을 스탑으로, TP는 비활성(신호 청산 통일).
    """

    def __init__(
        self,
        config: PsarRsiConfig,
        exchange: ExchangeClient,
        reporter: Optional[TradeReporter] = None,
        env: Optional[dict] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.config = config
        self.exchange = exchange
        self.logger = get_logger("PsarRsiTrader")
        self.reporter = reporter or TradeReporter()
        self.df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.indicator_df = self.df.copy()
        self.db_path = "trading_data.db"
        self.env = env or {}
        self.risk_manager = risk_manager

    def _notify(self, message: str) -> None:
        send_telegram_message(self.env, message)

    async def handle_candle(self, candle: Candle):
        if not candle.closed:
            return
        self._append_candle(candle)
        await self._evaluate()

    def _append_candle(self, candle: Candle):
        row = {
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        if self.df.empty:
            self.df = pd.DataFrame([row])
        else:
            self.df.loc[len(self.df)] = row
        self.df = self.df.drop_duplicates(subset="timestamp", keep="last")
        if len(self.df) > self.config.max_bars:
            self.df = self.df.iloc[-self.config.max_bars :]

    async def _evaluate(self):
        min_bars = max(self.config.ema_length, self.config.rsi_length, self.config.swing_lookback) + 2
        if len(self.df) < min_bars:
            return

        self.indicator_df = compute_psar_rsi_ema(
            self.df,
            ema_length=self.config.ema_length,
            rsi_length=self.config.rsi_length,
            psar_step=self.config.psar_step,
            psar_max_step=self.config.psar_max_step,
            use_heikin_ashi=self.config.use_heikin_ashi,
        )
        latest = self.indicator_df.iloc[-1]
        prev = self.indicator_df.iloc[-2]
        price = float(latest["close"])
        psar_value = float(latest.get("psar", 0.0))
        rsi_value = float(latest.get("rsi", 0.0))
        self.logger.info(
            "Internal | Price: %.2f | PSAR: %.4f | RSI: %.1f",
            price,
            psar_value,
            rsi_value,
        )
        rsi_near = rsi_value <= 32 or rsi_value >= 68
        psar_near = price > 0 and abs(price - psar_value) / price <= 0.002
        if rsi_near or psar_near:
            self.logger.info(
                "Signal soon? RSI=%.1f PSAR=%.4f price=%.2f",
                rsi_value,
                psar_value,
                price,
            )

        position = self.exchange.get_position(self.config.symbol)
        if position is not None:
            await self._manage_open_position(latest)
            position = self.exchange.get_position(self.config.symbol)  # refresh after potential exit
        if position is None:
            await self._check_entries(latest, prev)

    async def _check_entries(self, latest, prev):
        long_signal = bool(latest.get("psar_flip_long")) and latest["close"] > latest["ema"] and latest["rsi"] > 50
        short_signal = bool(latest.get("psar_flip_short")) and latest["close"] < latest["ema"] and latest["rsi"] < 50

        if long_signal:
            await self._open_position(latest, side="long")
        elif short_signal:
            await self._open_position(latest, side="short")

    def _swing_stop(self, side: str) -> Optional[float]:
        if self.df.empty:
            return None
        window = self.df.iloc[-self.config.swing_lookback :]
        if window.empty:
            return None
        if self.config.use_heikin_ashi and {"ha_high", "ha_low"}.issubset(self.indicator_df.columns):
            window = self.indicator_df.iloc[-self.config.swing_lookback :]
            if side == "long":
                return float(window["ha_low"].min())
            return float(window["ha_high"].max())
        if side == "long":
            return float(window["low"].min())
        return float(window["high"].max())

    async def _open_position(self, latest, side: str):
        swing_stop = self._swing_stop(side)
        if swing_stop is None:
            return

        entry = float(latest["close"])
        psar_value = float(latest.get("psar", 0.0))
        rsi_value = float(latest.get("rsi", 0.0))
        risk_per_unit = abs(entry - swing_stop)
        if risk_per_unit <= 0:
            return

        equity = await self.exchange.fetch_equity()
        available_balance = await self.exchange.fetch_available_balance()

        if self.risk_manager:
            qty, reason = await self.risk_manager.size_and_validate(
                symbol=self.config.symbol,
                entry_price=entry,
                stop_price=swing_stop,
                equity=equity,
                available_balance=available_balance,
            )
            if qty is None:
                self.logger.info("Order skipped (%s): %s", reason, self.config.symbol)
                return
        else:
            risk_capital = equity * (self.config.risk_pct / 100) * max(self.config.leverage, 0.01)
            qty = max(risk_capital / risk_per_unit, 0.0)
            if qty <= 0:
                return

        # TP는 현재 비활성. 신호(PSAR flip) 청산으로 통일.
        if side == "long":
            stop_price = swing_stop
            target_price = entry + self.config.risk_reward * risk_per_unit
        else:
            stop_price = swing_stop
            target_price = entry - self.config.risk_reward * risk_per_unit

        trail_offset = risk_per_unit
        await self.exchange.enter_position(
            symbol=self.config.symbol,
            side=side,
            qty=qty,
            stop_price=stop_price,
            tp1_price=target_price,
            runner_price=target_price,
            trail_offset=trail_offset,
            entry_price=entry,
        )
        if self.risk_manager:
            self.risk_manager.mark_open(self.config.symbol)
        signal_type = "BUY" if side == "long" else "SELL"
        log_trade_signal(signal_type, self.config.symbol, entry, psar_value, rsi_value, balance=equity)
        log_trade_db(
            self.db_path,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.config.symbol,
            side,
            entry,
            qty,
            0.0,
            signal_type,
        )
        self._notify(
            f"[ENTRY] {signal_type} {self.config.symbol}\n"
            f"entry={entry:.2f} qty={qty:.6f}\n"
            f"stop={stop_price:.2f} target={target_price:.2f}"
        )
        self.logger.info(
            "Enter %s | entry=%.4f stop=%.4f target=%.4f risk=%.4f qty=%.6f",
            side,
            entry,
            stop_price,
            target_price,
            risk_per_unit,
            qty,
        )

    def _record_exit(self, position, exit_price: float, reason: str):
        direction = 1 if position.side == "long" else -1
        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100 * direction
        log_trade_db(
            self.db_path,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.config.symbol,
            position.side,
            exit_price,
            position.qty,
            pnl_pct,
            reason,
        )
        if self.risk_manager:
            self.risk_manager.mark_closed(self.config.symbol)
        self._notify(
            f"[EXIT] {position.side.upper()} {self.config.symbol}\n"
            f"exit={exit_price:.2f} pnl={pnl_pct:.2f}%\n"
            f"reason={reason}"
        )

    async def _manage_open_position(self, latest):
        position = self.exchange.get_position(self.config.symbol)
        if position is None:
            return

        position.update_extremes(latest["high"], latest["low"])
        price = float(latest["close"])

        if position.side == "long":
            # stop loss
            if latest["low"] <= position.stop_price:
                self._record_exit(position, float(position.stop_price), "Stop - swing low")
                await self.exchange.close_position(self.config.symbol, None, position.stop_price, "Stop - swing low")
                return
            # take profit
            if latest["high"] >= position.runner_price:
                self._record_exit(position, float(position.runner_price), "Take Profit 2R")
                await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Take Profit 2R")
                return
            # optional PSAR flip exit
            if self.config.exit_on_psar_flip and latest.get("psar_flip_short", False):
                self._record_exit(position, price, "PSAR flip exit")
                await self.exchange.close_position(self.config.symbol, None, price, "PSAR flip exit")
                return
            # tighten stop to new swing lows
            new_stop = self._swing_stop("long")
            if new_stop and new_stop > position.stop_price and new_stop < price:
                position.stop_price = new_stop
        else:
            if latest["high"] >= position.stop_price:
                self._record_exit(position, float(position.stop_price), "Stop - swing high")
                await self.exchange.close_position(self.config.symbol, None, position.stop_price, "Stop - swing high")
                return
            if latest["low"] <= position.runner_price:
                self._record_exit(position, float(position.runner_price), "Take Profit 2R")
                await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Take Profit 2R")
                return
            if self.config.exit_on_psar_flip and latest.get("psar_flip_long", False):
                self._record_exit(position, price, "PSAR flip exit")
                await self.exchange.close_position(self.config.symbol, None, price, "PSAR flip exit")
                return
            new_stop = self._swing_stop("short")
            if new_stop and new_stop < position.stop_price and new_stop > price:
                position.stop_price = new_stop

    async def warmup_with_rest(self, bars: int = 500):
        rest_client = BinanceRestClient()
        candles = await rest_client.fetch_klines(self.config.symbol, self.config.interval, limit=bars)
        for entry in candles:
            candle = Candle(
                timestamp=entry["timestamp"],
                open=entry["open"],
                high=entry["high"],
                low=entry["low"],
                close=entry["close"],
                volume=entry["volume"],
                closed=True,
            )
            self._append_candle(candle)
        self.logger.info("Bootstrapped %d candles via REST", len(candles))

    async def run_live(self):
        stream = BinanceCandleStream(self.config.symbol, self.config.interval, logger=self.logger)

        async def handle(candle: Candle):
            await self.handle_candle(candle)

        await stream.start(handle)

    async def run_paper_test(self, bars: int = 500) -> float:
        rest_client = BinanceRestClient()
        candles = await rest_client.fetch_klines(self.config.symbol, self.config.interval, limit=bars)
        self.df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.indicator_df = self.df.copy()
        self.logger.info("Running offline paper simulation on %d bars", len(candles))
        for entry in candles:
            candle = Candle(
                timestamp=entry["timestamp"],
                open=entry["open"],
                high=entry["high"],
                low=entry["low"],
                close=entry["close"],
                volume=entry["volume"],
                closed=True,
            )
            await self.handle_candle(candle)
        equity = await self.exchange.fetch_equity()
        self.logger.info("Paper test completed. Final equity %.2f", equity)
        return equity


def parse_args():
    parser = argparse.ArgumentParser(description="PSAR + EMA200 + RSI(50) ?? ???")
    parser.add_argument("--symbol", default=None, help="?? ?? (?: BTCUSDT)")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols (e.g., BTCUSDT,SOLUSDT)")
    parser.add_argument("--interval", default=None, help="???? ?? ?? (?? 1h)")
    parser.add_argument("--risk-pct", type=float, default=None, help="????? ??? % (?? 1.0)")
    parser.add_argument("--rr", type=float, default=None, help="???-??? ?? (?? 2.0)")
    parser.add_argument("--swing", type=int, default=None, help="?? ??? ?? ? ? (?? 5)")
    parser.add_argument("--live", action="store_true", help="???? ?? ??? WebSocket ??")
    parser.add_argument("--paper", dest="paper_mode", action="store_true", help="??? ???(??) ??")
    parser.add_argument("--real", dest="paper_mode", action="store_false", help="??? ??? ??")
    parser.set_defaults(paper_mode=None)
    parser.add_argument("--paper-bars", type=int, default=750, help="Number of bars for offline paper test")
    parser.add_argument("--test-order", action="store_true", help="Force a test order (buy then sell after 10s)")
    return parser.parse_args()


def _parse_symbols(args, env: dict):
    raw = args.symbols or env.get("PSAR_RSI_SYMBOLS")
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    symbol = args.symbol or env.get("PSAR_RSI_SYMBOL") or env.get("BTC_TREND_SYMBOL") or "BTCUSDT"
    return [symbol.upper()]


async def main():
    init_trade_log()
    args = parse_args()
    env = load_env()
    init_sqlite()
    app_logger = get_app_logger()

    symbols = _parse_symbols(args, env)
    symbol = symbols[0]
    interval = args.interval or env.get("PSAR_RSI_INTERVAL") or "1h"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = (
        "REAL"
        if (
            args.paper_mode is False
            or (
                args.paper_mode is None
                and (env.get("PSAR_RSI_PAPER_MODE") or env.get("BTC_TREND_PAPER_MODE", "true")).lower()
                in ("0", "false", "no", "off")
            )
        )
        else "PAPER"
    )
    send_telegram_message(
        env,
        "⚡ PSAR RSI Bot Online\n"
        f"time={now}\n"
        f"mode={mode}\n"
        f"symbols={','.join(symbols)} interval={interval}",
    )
    risk_pct_env = env.get("PSAR_RSI_RISK_PCT") or env.get("BTC_TREND_RISK_PCT")
    risk_pct = args.risk_pct if args.risk_pct is not None else float(risk_pct_env or 1.0)
    rr_env = env.get("PSAR_RSI_RR") or env.get("PSAR_RSI_RISK_REWARD")
    risk_reward = args.rr if args.rr is not None else float(rr_env or 2.0)
    swing_env = env.get("PSAR_RSI_SWING_LOOKBACK")
    swing_lookback = args.swing if args.swing is not None else int(swing_env or 5)
    leverage_env = env.get("PSAR_RSI_LEVERAGE") or env.get("BTC_TREND_LEVERAGE")
    leverage = float(leverage_env or 1.0)
    exit_on_flip_env = env.get("PSAR_RSI_EXIT_ON_FLIP", "true").lower()
    exit_on_flip = exit_on_flip_env not in ("0", "false", "no", "off")

    base_config = PsarRsiConfig(
        symbol=symbol,
        interval=interval,
        risk_pct=risk_pct,
        risk_reward=risk_reward,
        swing_lookback=swing_lookback,
        leverage=leverage,
        exit_on_psar_flip=exit_on_flip,
        use_heikin_ashi=True,
    )

    max_notional_map = parse_max_notional_map(env.get("PSAR_RSI_MAX_NOTIONALS"))
    reserve = float(env.get("PSAR_RSI_RESERVE", "0") or 0)
    margin_buffer = float(env.get("PSAR_RSI_MARGIN_BUFFER", "0.05") or 0.05)
    cooldown_sec = int(env.get("PSAR_RSI_ALERT_COOLDOWN_SEC", "900") or 900)
    rest_client = BinanceRestClient()
    risk_manager = RiskManager(
        rest_client=rest_client,
        notify_fn=lambda msg: send_telegram_message(env, msg),
        max_notional_by_symbol=max_notional_map,
        reserve=reserve,
        leverage=leverage,
        risk_pct=risk_pct,
        margin_buffer=margin_buffer,
        cooldown_sec=cooldown_sec,
    )

    reporter = TradeReporter()
    if args.paper_mode is not None:
        paper_mode = args.paper_mode
    else:
        env_paper = env.get("PSAR_RSI_PAPER_MODE") or env.get("BTC_TREND_PAPER_MODE", "true")
        paper_mode = env_paper.lower() not in ("0", "false", "no", "off")

    notifier = TelegramNotifier(env)
    if paper_mode:
        exchange_client: ExchangeClient = PaperExchangeClient(
            starting_equity=10000.0,
            reporter=reporter,
            notifier=notifier,
        )
    else:
        api_key = env.get("BINANCE_API_KEY") or env.get("API_KEY")
        api_secret = env.get("BINANCE_API_SECRET") or env.get("SECRET_KEY")
        if not api_key or not api_secret:
            raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for real trading mode")
        exchange_client = BinanceLiveExchange(
            api_key=api_key,
            api_secret=api_secret,
            reporter=reporter,
            notifier=notifier,
            alert_cb=lambda msg: send_telegram_message(env, msg),
        )

    bots = []
    for sym in symbols:
        cfg = PsarRsiConfig(
            symbol=sym,
            interval=base_config.interval,
            risk_pct=base_config.risk_pct,
            risk_reward=base_config.risk_reward,
            swing_lookback=base_config.swing_lookback,
            leverage=base_config.leverage,
            exit_on_psar_flip=base_config.exit_on_psar_flip,
            use_heikin_ashi=base_config.use_heikin_ashi,
        )
        bots.append(PsarRsiTrader(cfg, exchange_client, reporter=reporter, env=env, risk_manager=risk_manager))

    try:
        if args.test_order:
            candles = await rest_client.fetch_klines(symbol, interval, limit=2)
            last_close = candles[-1]["close"] if candles else 0.0
            if last_close <= 0:
                raise RuntimeError("Unable to fetch price for test order")
            available_balance = await exchange_client.fetch_available_balance()
            equity = await exchange_client.fetch_equity()
            qty, reason = await risk_manager.size_and_validate(
                symbol=symbol,
                entry_price=last_close,
                stop_price=last_close * 0.98,
                equity=equity,
                available_balance=available_balance,
            )
            if qty is None:
                raise RuntimeError(f"Test order blocked: {reason}")
            await exchange_client.enter_position(
                symbol=symbol,
                side="long",
                qty=qty,
                stop_price=last_close * 0.98,
                tp1_price=last_close * 1.02,
                runner_price=last_close * 1.02,
                trail_offset=last_close * 0.01,
                entry_price=last_close,
            )
            await asyncio.sleep(10)
            candles = await rest_client.fetch_klines(symbol, interval, limit=2)
            last_close = candles[-1]["close"] if candles else last_close
            await exchange_client.close_position(symbol, None, last_close, "Test order exit")
            send_telegram_message(env, "✅ Test order completed (buy → sell)")
            return

        try:
            if args.live:
                tasks = []
                for bot in bots:
                    tasks.append(bot.warmup_with_rest(bars=500))
                if tasks:
                    await asyncio.gather(*tasks)
                await asyncio.gather(*(bot.run_live() for bot in bots))
            else:
                await asyncio.gather(*(bot.run_paper_test(bars=args.paper_bars) for bot in bots))
        except Exception as exc:
            app_logger.error("System error: %s", exc)
            send_telegram_message(env, f"🚨 Bot error: {exc}")
            raise
    finally:
        close_fn = getattr(exchange_client, "close", None)
        if callable(close_fn):
            await close_fn()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

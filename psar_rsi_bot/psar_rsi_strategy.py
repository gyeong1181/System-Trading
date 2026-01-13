from __future__ import annotations

import argparse
import asyncio
import csv
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from exchange import (
    BinanceCandleStream,
    BinanceLiveExchange,
    BinanceRestClient,
    ExchangeClient,
    PaperExchangeClient,
)
from indicators import compute_psar_rsi_ema
from reports import TradeReporter
from utils import Candle, get_logger, load_env


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


class PsarRsiTrader:
    """
    트레이딩뷰식 파라볼릭 SAR + EMA200 + RSI(50) 전략.
    진입 조건(마감봉 기준):
      - 롱: PSAR가 상승 전환 AND 종가 > EMA200 AND RSI > 50
      - 숏: PSAR가 하락 전환 AND 종가 < EMA200 AND RSI < 50
    리스크: 최근 스윙 고점/저점을 스탑으로, 기본 2R 목표가.
    """

    def __init__(self, config: PsarRsiConfig, exchange: ExchangeClient, reporter: Optional[TradeReporter] = None):
        self.config = config
        self.exchange = exchange
        self.logger = get_logger("PsarRsiTrader")
        self.reporter = reporter or TradeReporter()
        self.df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.indicator_df = self.df.copy()

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
        )
        latest = self.indicator_df.iloc[-1]
        prev = self.indicator_df.iloc[-2]

        position = self.exchange.position
        if position is not None:
            await self._manage_open_position(latest)
            position = self.exchange.position  # refresh after potential exit
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
        risk_capital = equity * (self.config.risk_pct / 100) * max(self.config.leverage, 0.01)
        qty = max(risk_capital / risk_per_unit, 0.0)
        if qty <= 0:
            return

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
        signal_type = "BUY" if side == "long" else "SELL"
        log_trade_signal(signal_type, self.config.symbol, entry, psar_value, rsi_value, balance=equity)
        self.logger.info(
            "Enter %s | entry=%.4f stop=%.4f target=%.4f risk=%.4f qty=%.6f",
            side,
            entry,
            stop_price,
            target_price,
            risk_per_unit,
            qty,
        )

    async def _manage_open_position(self, latest):
        position = self.exchange.position
        if position is None:
            return

        position.update_extremes(latest["high"], latest["low"])
        price = float(latest["close"])

        if position.side == "long":
            # stop loss
            if latest["low"] <= position.stop_price:
                await self.exchange.close_position(self.config.symbol, None, position.stop_price, "Stop - swing low")
                return
            # take profit
            if latest["high"] >= position.runner_price:
                await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Take Profit 2R")
                return
            # optional PSAR flip exit
            if self.config.exit_on_psar_flip and latest.get("psar_flip_short", False):
                await self.exchange.close_position(self.config.symbol, None, price, "PSAR flip exit")
                return
            # tighten stop to new swing lows
            new_stop = self._swing_stop("long")
            if new_stop and new_stop > position.stop_price and new_stop < price:
                position.stop_price = new_stop
        else:
            if latest["high"] >= position.stop_price:
                await self.exchange.close_position(self.config.symbol, None, position.stop_price, "Stop - swing high")
                return
            if latest["low"] <= position.runner_price:
                await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Take Profit 2R")
                return
            if self.config.exit_on_psar_flip and latest.get("psar_flip_long", False):
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
    parser = argparse.ArgumentParser(description="PSAR + EMA200 + RSI(50) 전략 실행기")
    parser.add_argument("--symbol", default=None, help="거래 심볼 (예: BTCUSDT)")
    parser.add_argument("--interval", default=None, help="바이낸스 캔들 주기 (기본 1h)")
    parser.add_argument("--risk-pct", type=float, default=None, help="트레이드당 리스크 % (기본 1.0)")
    parser.add_argument("--rr", type=float, default=None, help="리스크-리워드 배수 (기본 2.0)")
    parser.add_argument("--swing", type=int, default=None, help="스윙 고저점 탐색 봉 수 (기본 5)")
    parser.add_argument("--live", action="store_true", help="바이낸스 선물 실시간 WebSocket 사용")
    parser.add_argument("--paper", dest="paper_mode", action="store_true", help="무조건 페이퍼(모의) 모드")
    parser.add_argument("--real", dest="paper_mode", action="store_false", help="무조건 실거래 모드")
    parser.set_defaults(paper_mode=None)
    parser.add_argument("--paper-bars", type=int, default=750, help="Number of bars for offline paper test")
    return parser.parse_args()


async def main():
    init_trade_log()
    args = parse_args()
    env = load_env()

    symbol = args.symbol or env.get("PSAR_RSI_SYMBOL") or env.get("BTC_TREND_SYMBOL") or "BTCUSDT"
    interval = args.interval or env.get("PSAR_RSI_INTERVAL") or "1h"
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

    config = PsarRsiConfig(
        symbol=symbol,
        interval=interval,
        risk_pct=risk_pct,
        risk_reward=risk_reward,
        swing_lookback=swing_lookback,
        leverage=leverage,
        exit_on_psar_flip=exit_on_flip,
    )

    reporter = TradeReporter()
    if args.paper_mode is not None:
        paper_mode = args.paper_mode
    else:
        env_paper = env.get("PSAR_RSI_PAPER_MODE") or env.get("BTC_TREND_PAPER_MODE", "true")
        paper_mode = env_paper.lower() not in ("0", "false", "no", "off")

    if paper_mode:
        exchange_client: ExchangeClient = PaperExchangeClient(starting_equity=10000.0, reporter=reporter)
    else:
        api_key = env.get("BINANCE_API_KEY") or env.get("API_KEY")
        api_secret = env.get("BINANCE_API_SECRET") or env.get("SECRET_KEY")
        if not api_key or not api_secret:
            raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for real trading mode")
        exchange_client = BinanceLiveExchange(api_key=api_key, api_secret=api_secret, reporter=reporter)

    bot = PsarRsiTrader(config, exchange_client, reporter=reporter)

    try:
        if args.live:
            await bot.warmup_with_rest(bars=500)
            await bot.run_live()
        else:
            await bot.run_paper_test(bars=args.paper_bars)
    finally:
        close_fn = getattr(exchange_client, "close", None)
        if callable(close_fn):
            await close_fn()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

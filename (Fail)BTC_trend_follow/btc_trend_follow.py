"""
BTC 추세추종 전략 - 원본 메인 파일
- systemd 서비스에서 직접 실행할 때 사용
- Docker 사용 시에는 main.py를 사용 (Telegram/S3/CloudWatch 통합)
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from exchange import (
    BinanceCandleStream,
    BinanceRestClient,
    BinanceLiveExchange,
    ExchangeClient,
    PaperExchangeClient,
)
from indicators import compute_indicators
from risk import RiskConfig, RiskManager
from reports import TradeReporter
from utils import Candle, get_logger, load_env


@dataclass
class StrategyConfig:
    symbol: str = "BTCUSDT"
    interval: str = "4h"
    fast_len: int = 20
    slow_len: int = 50
    adx_len: int = 14
    atr_len: int = 14
    risk_pct: float = 1.0
    leverage: float = 1.0
    use_short: bool = False
    adx_threshold: float = 15.0
    max_bars: int = 2000


class BTCTrendFollower:
    def __init__(self, config: StrategyConfig, exchange: ExchangeClient):
        self.config = config
        self.exchange = exchange
        self.logger = get_logger("BTCTrendFollower")
        self.risk_manager = RiskManager(
            RiskConfig(
                risk_pct=config.risk_pct,
                atr_stop_multiple=2.2,
                tp1_multiple=2.5,
                runner_multiple=4.0,
                trail_multiple=2.5,
                leverage=config.leverage,
            )
        )
        self.df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.indicator_df = self.df.copy()

    async def handle_candle(self, candle: Candle):
        if not candle.closed:
            return
        self._append_candle(candle)
        await self._evaluate_strategy()

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

    async def _evaluate_strategy(self):
        if len(self.df) < max(self.config.fast_len, self.config.slow_len) + 2:
            return

        self.indicator_df = compute_indicators(
            self.df,
            fast_len=self.config.fast_len,
            slow_len=self.config.slow_len,
            adx_len=self.config.adx_len,
            atr_len=self.config.atr_len,
        )
        latest = self.indicator_df.iloc[-1]
        prev = self.indicator_df.iloc[-2]
        position = self.exchange.position

        if position is not None:
            await self._manage_open_position(latest, prev)
            position = self.exchange.position  # refresh after management

        if position is None or position.side == "short":
            await self._check_long_entry(latest, prev, position)
            position = self.exchange.position

        if self.config.use_short and (position is None or position.side == "long"):
            await self._check_short_entry(latest, prev, position)

    async def _check_long_entry(self, latest, prev, position):
        cross_up = prev["ema_fast"] <= prev["ema_slow"] and latest["ema_fast"] > latest["ema_slow"]
        trend_ok = latest["ema_fast"] > latest["ema_slow"]
        adx_ok = latest["adx"] > self.config.adx_threshold
        if cross_up and trend_ok and adx_ok:
            if position and position.side == "short":
                await self.exchange.close_position(self.config.symbol, None, latest["close"], "Reverse to Long")
            await self._open_position(latest, side="long")

    async def _check_short_entry(self, latest, prev, position):
        cross_down = prev["ema_fast"] >= prev["ema_slow"] and latest["ema_fast"] < latest["ema_slow"]
        trend_ok = latest["ema_fast"] < latest["ema_slow"]
        adx_ok = latest["adx"] > self.config.adx_threshold
        if cross_down and trend_ok and adx_ok:
            if position and position.side == "long":
                await self.exchange.close_position(self.config.symbol, None, latest["close"], "Reverse to Short")
            await self._open_position(latest, side="short")

    async def _open_position(self, latest, side: str):
        atr_value = latest["atr"]
        if atr_value <= 0:
            return
        equity = await self.exchange.fetch_equity()
        qty, atr_stop = self.risk_manager.position_size(equity, atr_value)
        tp1_target, runner_target = self.risk_manager.take_profit_targets(atr_stop)
        trail_offset = self.risk_manager.trail_offset(atr_value)
        if side == "long":
            stop_price = latest["close"] - atr_stop
            tp1_price = latest["close"] + tp1_target
            runner_price = latest["close"] + runner_target
        else:
            stop_price = latest["close"] + atr_stop
            tp1_price = latest["close"] - tp1_target
            runner_price = latest["close"] - runner_target
        await self.exchange.enter_position(
            symbol=self.config.symbol,
            side=side,
            qty=qty,
            stop_price=stop_price,
            tp1_price=tp1_price,
            runner_price=runner_price,
            trail_offset=trail_offset,
            entry_price=latest["close"],
        )

    async def _manage_open_position(self, latest, prev):
        position = self.exchange.position
        if position is None:
            return
        position.update_extremes(latest["high"], latest["low"])

        if position.side == "long":
            await self._manage_long_position(position, latest, prev)
        else:
            await self._manage_short_position(position, latest, prev)

    async def _manage_long_position(self, position, latest, prev):
        position.stop_price = max(position.stop_price, position.highest - position.trail_offset)
        if latest["low"] <= position.stop_price:
            await self.exchange.close_position(self.config.symbol, None, position.stop_price, "ATR Stop/Trail")
            return
        if not position.filled_tp1 and latest["high"] >= position.tp1_price:
            qty = min(position.qty, position.initial_qty * 0.5)
            await self.exchange.close_position(self.config.symbol, qty, position.tp1_price, "TP1 Hit")
            position.filled_tp1 = True
        if latest["high"] >= position.runner_price:
            await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Runner Target")
            return
        flip_now = latest["ema_fast"] < latest["ema_slow"]
        flip_prev = prev["ema_fast"] < prev["ema_slow"]
        if flip_now and flip_prev:
            await self.exchange.close_position(self.config.symbol, None, latest["close"], "EMA Flip x2")

    async def _manage_short_position(self, position, latest, prev):
        position.stop_price = min(position.stop_price, position.lowest + position.trail_offset)
        if latest["high"] >= position.stop_price:
            await self.exchange.close_position(self.config.symbol, None, position.stop_price, "ATR Stop/Trail")
            return
        if not position.filled_tp1 and latest["low"] <= position.tp1_price:
            qty = min(position.qty, position.initial_qty * 0.5)
            await self.exchange.close_position(self.config.symbol, qty, position.tp1_price, "TP1 Hit")
            position.filled_tp1 = True
        if latest["low"] <= position.runner_price:
            await self.exchange.close_position(self.config.symbol, None, position.runner_price, "Runner Target")
            return
        flip_now = latest["ema_fast"] > latest["ema_slow"]
        flip_prev = prev["ema_fast"] > prev["ema_slow"]
        if flip_now and flip_prev:
            await self.exchange.close_position(self.config.symbol, None, latest["close"], "EMA Flip x2")

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
    parser = argparse.ArgumentParser(description="BTC 추세추종 (AuraBot v1.6.1 Python 포팅)")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--interval", default=None, help="Binance kline interval (default 4h)")
    parser.add_argument("--risk-pct", type=float, default=None)
    parser.add_argument("--leverage", type=float, default=None, help="Position leverage (default 1.0)")
    parser.add_argument("--use-short", action="store_true")
    parser.add_argument("--live", action="store_true", help="Run live with Binance Futures websocket")
    parser.add_argument(
        "--paper",
        dest="paper_mode",
        action="store_true",
        help="Force paper (fake money) mode",
    )
    parser.add_argument(
        "--real",
        dest="paper_mode",
        action="store_false",
        help="Force real-money Binance trading",
    )
    parser.set_defaults(paper_mode=None)
    parser.add_argument("--paper-bars", type=int, default=750, help="Number of bars for paper test bootstrap")
    return parser.parse_args()


async def main():
    args = parse_args()
    env = load_env()
    symbol = args.symbol or env.get("BTC_TREND_SYMBOL") or env.get("AURABOT_SYMBOL", "BTCUSDT")
    interval = args.interval or env.get("BTC_TREND_INTERVAL") or env.get("AURABOT_INTERVAL", "4h")
    env_risk = env.get("BTC_TREND_RISK_PCT") or env.get("AURABOT_RISK_PCT")
    risk_pct = args.risk_pct if args.risk_pct is not None else float(env_risk or 1.0)
    env_leverage = env.get("BTC_TREND_LEVERAGE") or env.get("AURABOT_LEVERAGE")
    leverage = args.leverage if args.leverage is not None else float(env_leverage or 1.0)
    use_short_env = (env.get("BTC_TREND_USE_SHORT") or env.get("AURABOT_USE_SHORT", "false")).lower()
    use_short = args.use_short or use_short_env in ("1", "true", "yes", "on")
    env_paper = env.get("BTC_TREND_PAPER_MODE") or env.get("AURABOT_PAPER_MODE", "true")
    if args.paper_mode is not None:
        paper_mode = args.paper_mode
    else:
        paper_mode = env_paper.lower() not in ("0", "false", "no", "off")
    config = StrategyConfig(
        symbol=symbol,
        interval=interval,
        risk_pct=risk_pct,
        leverage=leverage,
        use_short=use_short,
    )
    reporter = TradeReporter()
    if paper_mode:
        exchange_client: ExchangeClient = PaperExchangeClient(starting_equity=10000.0, reporter=reporter)
    else:
        api_key = env.get("BINANCE_API_KEY") or env.get("API_KEY")
        api_secret = env.get("BINANCE_API_SECRET") or env.get("SECRET_KEY")
        if not api_key or not api_secret:
            raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for real trading mode")
        exchange_client = BinanceLiveExchange(api_key=api_key, api_secret=api_secret, reporter=reporter)
    bot = BTCTrendFollower(config, exchange_client)

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

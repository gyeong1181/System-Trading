"""Entry point wiring together data, signals, risk, and alerts."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, Tuple

import pandas as pd

from data.binance_client import DEFAULT_SYMBOLS, BinanceClient
from signals.ema_filter import ema_signal
from signals.fibonacci import fibonacci_levels
from signals.fractals import fractal_signal
from signals.rsi_divergence import rsi_divergence_signal
from risk.risk_manager import RiskManager
from alerts.telegram_bot import TelegramNotifier

LOGGER = logging.getLogger("swing_mvp")
TECH_WEIGHT = 0.4
MICRO_WEIGHT = 0.4
MACRO_WEIGHT = 0.2


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def compute_scores(frames: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, object]]:
    account_balance = float(os.getenv("ACCOUNT_BALANCE", "10000"))
    realized_losses = float(os.getenv("DAILY_REALIZED_LOSS", "0"))
    risk_manager = RiskManager(account_balance=account_balance)

    symbol_results: Dict[str, Dict[str, object]] = {}

    for alias, frame in frames.items():
        if frame.empty:
            LOGGER.warning("%s returned no candles", alias)
            continue

        ema_result = ema_signal(frame)
        rsi_result = rsi_divergence_signal(frame)
        fib_result = fibonacci_levels(frame)
        fractal_result = fractal_signal(frame)

        technical_components = [ema_result.score, rsi_result.score, fib_result.score, fractal_result.score]
        technical_score = sum(technical_components) / len(technical_components)

        micro_score = 0.0  # placeholder for market microstructure inputs
        macro_score = 0.0  # placeholder for macro / sentiment inputs
        weighted_score = (
            technical_score * TECH_WEIGHT
            + micro_score * MICRO_WEIGHT
            + macro_score * MACRO_WEIGHT
        )

        direction = "LONG" if technical_score >= 0 else "SHORT"
        latest_close = float(frame["close"].iloc[-1])
        recent_low = float(frame["low"].tail(12).min())
        recent_high = float(frame["high"].tail(12).max())

        if direction == "LONG":
            stop = min(recent_low, latest_close * 0.99)
            risk = max(latest_close - stop, 1e-6)
            target = latest_close + max(risk * risk_manager.min_rr, latest_close * 0.005)
        else:
            stop = max(recent_high, latest_close * 1.01)
            risk = max(stop - latest_close, 1e-6)
            target = latest_close - max(risk * risk_manager.min_rr, latest_close * 0.005)

        trade_plan = risk_manager.build_trade_plan(latest_close, stop, target, realized_losses)

        probability = round(max(min(50 + technical_score * 20, 90), 10), 1)
        leverage = round(max(1.0, min(5.0, abs(technical_score) * 5)), 2)

        symbol_results[alias] = {
            "symbol": alias,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "technical_score": round(technical_score, 3),
            "composite_score": round(weighted_score, 3),
            "probability": probability,
            "components": {
                "ema": {"score": ema_result.score, "summary": ema_result.summary, "latest": ema_result.extra.get("latest")},
                "rsi_divergence": {"score": rsi_result.score, "summary": rsi_result.summary},
                "fibonacci": {"score": fib_result.score, "summary": fib_result.summary},
                "fractals": {"score": fractal_result.score, "summary": fractal_result.summary},
            },
            "entry": latest_close,
            "stop": round(stop, 2),
            "target": round(target, 2),
            "position_size": round(trade_plan["position_size"], 4),
            "risk_reward": round(trade_plan["risk_reward"], 2),
            "risk_reward_ok": trade_plan["risk_reward_ok"],
            "daily_drawdown_ok": trade_plan["daily_drawdown_ok"],
            "max_risk_amount": round(trade_plan["max_risk_amount"], 2),
            "leverage": leverage,
        }

    return symbol_results


def build_alert_payload(result: Dict[str, object]) -> Dict[str, object]:
    return {
        "symbol": result["symbol"],
        "direction": result["direction"],
        "score": result["composite_score"],
        "probability": result["probability"],
        "entry": result["entry"],
        "stop": result["stop"],
        "target": result["target"],
        "position_size": result["position_size"],
        "leverage": result["leverage"],
    }


def fetch_data(client: BinanceClient, symbols: Iterable[Tuple[str, str]]) -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}
    for alias, ccxt_symbol in symbols:
        try:
            frames[alias] = client.fetch_ohlcv(ccxt_symbol)
        except RuntimeError as exc:
            LOGGER.error("Failed to fetch %s data: %s", alias, exc)
            frames[alias] = pd.DataFrame()
    return frames


def run_cycle(client: BinanceClient, notifier: TelegramNotifier) -> None:
    frames = fetch_data(client, DEFAULT_SYMBOLS.items())
    results = compute_scores(frames)

    for alias, result in results.items():
        LOGGER.info(
            "%s | dir=%s | score=%.3f | prob=%s | entry=%.2f | stop=%.2f | target=%.2f | size=%.4f",
            alias,
            result["direction"],
            result["composite_score"],
            result["probability"],
            result["entry"],
            result["stop"],
            result["target"],
            result["position_size"],
        )
        notifier.send_trade_alert(build_alert_payload(result))


def main() -> None:
    load_env_file()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    client = BinanceClient(timeframe="15m", limit=500)
    notifier = TelegramNotifier()

    run_once = os.getenv("RUN_ONCE", "true").lower() in {"1", "true", "yes"}
    interval = int(os.getenv("EVALUATION_INTERVAL_SECONDS", "900"))

    if run_once:
        run_cycle(client, notifier)
        return

    LOGGER.info("Starting continuous evaluation every %s seconds", interval)
    while True:
        run_cycle(client, notifier)
        time.sleep(interval)


if __name__ == "__main__":
    main()

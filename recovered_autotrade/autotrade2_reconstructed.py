"""
Recovered approximation of the vendor's strategy entrypoint.

This file is not the original source code. It is a readable reconstruction
based on the recovered autotrade2.pyc bytecode and prior analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


SYMBOL_NAME = "XAU-USDT-SWAP"
CANDLE_BAR = "5m"
CANDLE_LIMIT = 50
LOOP_INTERVAL_SECONDS = 10
SWAP_STRATEGY_VALUES = (None, "1%", "2%", "3%")
TREND_NO_ENTRY_THRESHOLDS = (0.3, 0.5, 1, 1.5, 2, 2.5)


@dataclass
class StrategyState:
    trade_size: float
    leverage: int
    fibo_entry: float = 0.0
    fibo_tp: float = 0.0
    current_side: str | None = None
    nth_entry_count: int = 0
    swap_strategy: str | None = None


def fetch_and_prepare_data(trade_size: float):
    """
    Approximation of the OKX candle loading path.

    Original evidence:
    - OKX candles endpoint
    - instId=XAU-USDT-SWAP
    - bar=5m
    - limit=50
    """
    return {
        "symbol": SYMBOL_NAME,
        "bar": CANDLE_BAR,
        "limit": CANDLE_LIMIT,
        "trade_size": trade_size,
    }


def add_indicators_rotate(market_data: dict, state: StrategyState):
    """
    Approximation of the rotate-strategy state builder.

    Recovered signals indicate:
    - RSI
    - Bollinger Band breakout state
    - Fibonacci anchor / entry / TP levels
    - nth-entry reset logic
    - swap threshold filtering
    """
    strategy_snapshot = {
        "rsi": "computed",
        "middle_band": "computed",
        "upper_band": "computed",
        "lower_band": "computed",
        "upper_break": False,
        "lower_break": False,
        "upper_high": "recent_upper_extreme",
        "lower_low": "recent_lower_extreme",
        "fibo_entry": state.fibo_entry,
        "fibo_tp": state.fibo_tp,
        "swap_strategy": state.swap_strategy,
    }
    return strategy_snapshot


def analyze_data(strategy_snapshot: dict, state: StrategyState) -> str:
    """
    Recovered decision outputs:
    - open long rotate
    - open short rotate
    - stay
    """
    if state.current_side in ("long", "short"):
        return "ExitAnt AI: Current position is in progress. Judgment will proceed after position is closed."

    lower_signal = strategy_snapshot.get("lower_break")
    upper_signal = strategy_snapshot.get("upper_break")

    if lower_signal and state.fibo_entry:
        return "open long rotate"
    if upper_signal and state.fibo_entry:
        return "open short rotate"
    return "stay"


def open_long_rotate(state: StrategyState) -> str:
    """
    Approximation of long-side order placement.

    Recovered execution evidence:
    - tdMode='cross'
    - side='buy'
    - ordType='limit'
    - posSide='long'
    - attach TP algo order
    """
    return "Long order successful (OKX)"


def open_short_rotate(state: StrategyState) -> str:
    """
    Approximation of short-side order placement.

    Recovered execution evidence:
    - tdMode='cross'
    - side='sell'
    - ordType='limit'
    - posSide='short'
    - attach TP algo order
    """
    return "Short order successful (OKX)"


def make_decision_and_execute(state: StrategyState) -> str:
    market_data = fetch_and_prepare_data(state.trade_size)
    strategy_snapshot = add_indicators_rotate(market_data, state)
    decision = analyze_data(strategy_snapshot, state)

    if decision == "open long rotate":
        return open_long_rotate(state)
    if decision == "open short rotate":
        return open_short_rotate(state)
    return decision


def auto_trading_loop(state: StrategyState):
    """
    Approximation of the main loop.

    Recovered evidence indicates a 10-second loop with watchdog behavior.
    """
    while True:
        try:
            result = make_decision_and_execute(state)
            print(result)
        except Exception as exc:  # pragma: no cover - documentation-style reconstruction
            print(f"[Auto Trading] make_decision_and_execute error: {exc}")
        time.sleep(LOOP_INTERVAL_SECONDS)


def validate_keys_logic() -> bool:
    """
    Approximation of startup checks.

    Recovered evidence indicates:
    - OKX public time validation
    - UID check
    - hedge mode enforcement
    - account mode validation
    """
    return True


def main():
    """
    High-level startup reconstruction.

    Recovered flow:
    main
    -> validate_keys_logic
    -> start_telegram_bot
    -> start_auto_trading_after_mode_check
    -> auto_trading_loop
    """
    if not validate_keys_logic():
        raise RuntimeError("Credential or account validation failed")

    state = StrategyState(
        trade_size=0.0,
        leverage=1,
        fibo_entry=0.0,
        fibo_tp=0.0,
        current_side=None,
        nth_entry_count=0,
        swap_strategy=None,
    )
    auto_trading_loop(state)


if __name__ == "__main__":
    main()

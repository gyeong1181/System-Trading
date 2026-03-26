from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import pandas as pd


@dataclass
class BacktestResult:
    metrics: dict[str, float]
    trades: list[dict[str, Any]]
    equity_curve: pd.DataFrame
    monthly_returns: list[dict[str, Any]]


def apply_fill_price(raw_price: float, side: str, slippage: float, is_entry: bool) -> float:
    direction = 1 if side == "long" else -1
    impact = slippage if is_entry else -slippage
    return raw_price * (1 + direction * impact)


def compute_drawdown(equity_curve: pd.Series) -> pd.Series:
    peak = equity_curve.cummax()
    return (equity_curve / peak) - 1.0


def compute_metrics(equity_curve: pd.DataFrame, trades: list[dict[str, Any]]) -> dict[str, float]:
    if equity_curve.empty:
        return {
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
            "trade_count": 0.0,
            "win_rate_pct": 0.0,
        }

    total_return_pct = (equity_curve["equity"].iloc[-1] / equity_curve["equity"].iloc[0]) - 1.0
    drawdown = compute_drawdown(equity_curve["equity"])
    gross_profit = sum(max(trade["pnl"], 0.0) for trade in trades)
    gross_loss = abs(sum(min(trade["pnl"], 0.0) for trade in trades))
    returns = equity_curve["equity"].pct_change().dropna()
    sharpe = 0.0
    if not returns.empty and returns.std() > 0:
        sharpe = (returns.mean() / returns.std()) * sqrt(365)
    win_rate = 0.0
    if trades:
        win_rate = sum(1 for trade in trades if trade["pnl"] > 0) / len(trades)
    return {
        "total_return_pct": float(total_return_pct),
        "max_drawdown_pct": float(drawdown.min()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float(gross_profit),
        "sharpe": float(sharpe),
        "trade_count": float(len(trades)),
        "win_rate_pct": float(win_rate),
    }


def compute_monthly_returns(equity_curve: pd.DataFrame) -> list[dict[str, Any]]:
    if equity_curve.empty:
        return []
    monthly = equity_curve.copy()
    monthly["month"] = monthly.index.to_period("M").astype(str)
    grouped = monthly.groupby("month")["equity"].agg(["first", "last"])
    rows = []
    for month, row in grouped.iterrows():
        change = (row["last"] / row["first"]) - 1 if row["first"] else 0.0
        rows.append({"month": month, "return_pct": float(change)})
    return rows


def run_backtest(
    strategy: object,
    frame: pd.DataFrame,
    symbol: str,
    params: dict[str, Any],
    fee_rate: float,
    slippage: float,
    risk_pct: float,
    starting_equity: float,
) -> BacktestResult:
    data = strategy.generate_signals(frame, params).copy()
    if data.empty:
        empty = pd.DataFrame(columns=["equity"])
        return BacktestResult(compute_metrics(empty, []), [], empty, [])

    data["symbol"] = symbol
    equity = starting_equity
    peak_equity = starting_equity
    position: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    for i in range(1, len(data)):
        prev_row = data.iloc[i - 1]
        row = data.iloc[i]
        current_time = data.index[i]

        if position is not None:
            position["bars_held"] += 1
            funding_rate = float(row.get("funding_rate", 0.0) or 0.0)
            if funding_rate != 0:
                direction = 1 if position["side"] == "long" else -1
                funding_cost = position["qty"] * row["open"] * funding_rate * direction
                equity -= funding_cost

            stop_hit = False
            stop_fill = None
            if position["side"] == "long" and row["low"] <= position["stop_price"]:
                stop_hit = True
                stop_fill = apply_fill_price(position["stop_price"], "long", slippage, is_entry=False)
            elif position["side"] == "short" and row["high"] >= position["stop_price"]:
                stop_hit = True
                stop_fill = apply_fill_price(position["stop_price"], "short", slippage, is_entry=False)

            if (
                not stop_hit
                and position["break_even_trigger_distance"] is not None
                and not position["break_even_armed"]
            ):
                if (
                    position["side"] == "long"
                    and row["high"] >= position["entry_price"] + position["break_even_trigger_distance"]
                ):
                    position["stop_price"] = max(position["stop_price"], position["entry_price"])
                    position["break_even_armed"] = True
                elif (
                    position["side"] == "short"
                    and row["low"] <= position["entry_price"] - position["break_even_trigger_distance"]
                ):
                    position["stop_price"] = min(position["stop_price"], position["entry_price"])
                    position["break_even_armed"] = True

            exit_flag = False
            if position["side"] == "long" and bool(prev_row["exit_long"]):
                exit_flag = True
                exit_price = apply_fill_price(float(row["open"]), "long", slippage, is_entry=False)
            elif position["side"] == "short" and bool(prev_row["exit_short"]):
                exit_flag = True
                exit_price = apply_fill_price(float(row["open"]), "short", slippage, is_entry=False)
            elif position["max_hold_bars"] is not None and position["bars_held"] >= position["max_hold_bars"]:
                exit_flag = True
                exit_price = apply_fill_price(float(row["open"]), position["side"], slippage, is_entry=False)
            else:
                exit_price = None

            if stop_hit:
                exit_flag = True
                exit_price = stop_fill
                reason = "stop"
            elif exit_flag and position["max_hold_bars"] is not None and position["bars_held"] >= position["max_hold_bars"]:
                reason = "time_stop"
            elif exit_flag:
                reason = "signal"
            else:
                reason = ""

            if exit_flag and exit_price is not None:
                if position["side"] == "long":
                    pnl = (exit_price - position["entry_price"]) * position["qty"]
                else:
                    pnl = (position["entry_price"] - exit_price) * position["qty"]
                fee = (position["entry_price"] + exit_price) * position["qty"] * fee_rate
                pnl -= fee
                equity += pnl
                trades.append(
                    {
                        "opened_at": position["opened_at"],
                        "closed_at": current_time,
                        "side": position["side"],
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "qty": position["qty"],
                        "pnl": pnl,
                        "fee": fee,
                        "reason": reason,
                    }
                )
                position = None

        if position is None:
            if bool(prev_row["entry_long"]):
                entry_price = apply_fill_price(float(row["open"]), "long", slippage, is_entry=True)
                stop_price = entry_price - float(prev_row["stop_distance"])
                risk_amount = equity * risk_pct
                qty = risk_amount / max(entry_price - stop_price, 1e-9)
                position = {
                    "side": "long",
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "qty": qty,
                    "opened_at": current_time,
                    "bars_held": 0,
                    "max_hold_bars": int(prev_row["time_stop_bars"]) if "time_stop_bars" in prev_row else None,
                    "break_even_trigger_distance": (
                        float(prev_row["break_even_trigger_distance"])
                        if "break_even_trigger_distance" in prev_row and float(prev_row["break_even_trigger_distance"]) > 0
                        else None
                    ),
                    "break_even_armed": False,
                }
                equity -= entry_price * qty * fee_rate
            elif bool(prev_row["entry_short"]):
                entry_price = apply_fill_price(float(row["open"]), "short", slippage, is_entry=True)
                stop_price = entry_price + float(prev_row["stop_distance"])
                risk_amount = equity * risk_pct
                qty = risk_amount / max(stop_price - entry_price, 1e-9)
                position = {
                    "side": "short",
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "qty": qty,
                    "opened_at": current_time,
                    "bars_held": 0,
                    "max_hold_bars": int(prev_row["time_stop_bars"]) if "time_stop_bars" in prev_row else None,
                    "break_even_trigger_distance": (
                        float(prev_row["break_even_trigger_distance"])
                        if "break_even_trigger_distance" in prev_row and float(prev_row["break_even_trigger_distance"]) > 0
                        else None
                    ),
                    "break_even_armed": False,
                }
                equity -= entry_price * qty * fee_rate

        mark_equity = equity
        if position is not None:
            if position["side"] == "long":
                unrealized = (row["close"] - position["entry_price"]) * position["qty"]
            else:
                unrealized = (position["entry_price"] - row["close"]) * position["qty"]
            mark_equity = equity + unrealized
        peak_equity = max(peak_equity, mark_equity)
        curve_rows.append({"timestamp": current_time, "equity": mark_equity, "drawdown": (mark_equity / peak_equity) - 1})

    equity_curve = pd.DataFrame(curve_rows).set_index("timestamp") if curve_rows else pd.DataFrame(columns=["equity"])
    metrics = compute_metrics(equity_curve, trades)
    monthly_returns = compute_monthly_returns(equity_curve)
    return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity_curve, monthly_returns=monthly_returns)

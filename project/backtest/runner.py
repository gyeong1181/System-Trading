"""Simple replay/backtest helpers leveraging logged signals."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    total_signals: int
    avg_score: float
    win_rate: float
    cumulative_return: float


def _load_signal_log(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Signal log not found: {path}")
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def run_replay(path: Path, *, leverage: float = 1.0) -> BacktestResult:
    """Replay historical signals with a heuristic PnL curve."""

    df = _load_signal_log(path)
    if df.empty:
        return BacktestResult(total_signals=0, avg_score=0.0, win_rate=0.0, cumulative_return=0.0)

    expected_returns = (df["score"] - 50) / 100 * 0.6
    rr = df.get("risk_reward", pd.Series([2.0] * len(df)))
    pnl_series = expected_returns * rr.clip(lower=1.0) * (leverage or 1.0) / 10
    wins = (pnl_series > 0).sum()
    total = len(df)
    cumulative = float(pnl_series.sum())

    return BacktestResult(
        total_signals=total,
        avg_score=float(df["score"].mean()),
        win_rate=float(wins / total),
        cumulative_return=cumulative,
    )


def _main(path: str) -> None:
    result = run_replay(Path(path))
    print(
        f"Signals: {result.total_signals}\n"
        f"Average score: {result.avg_score:.2f}\n"
        f"Win rate: {result.win_rate:.2%}\n"
        f"Cumulative return: {result.cumulative_return:.2f}"
    )


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import argparse

    parser = argparse.ArgumentParser(description="Replay signal logs to estimate performance.")
    parser.add_argument("path", type=str, help="Path to the signals CSV log.")
    parser.add_argument("--leverage", type=float, default=1.0, help="Override leverage assumption.")
    args = parser.parse_args()
    res = run_replay(Path(args.path), leverage=args.leverage)
    print(
        f"Signals: {res.total_signals}\n"
        f"Average score: {res.avg_score:.2f}\n"
        f"Win rate: {res.win_rate:.2%}\n"
        f"Cumulative return: {res.cumulative_return:.2f}"
    )


__all__ = ["BacktestResult", "run_replay"]

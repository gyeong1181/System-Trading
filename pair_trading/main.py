import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import ccxt
import numpy as np
import pandas as pd
import yaml
from loguru import logger
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from ta.trend import ADXIndicator
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def apply_profile(cfg: dict, profile: str | None) -> dict:
    if profile and cfg.get("profiles") and profile in cfg["profiles"]:
        override = cfg["profiles"][profile]
        merged = cfg.copy()
        merged.update(override)
        return merged
    return cfg


# ---------------------------------------------------------------------------
# Exchange / data utilities
# ---------------------------------------------------------------------------


def init_exchange() -> ccxt.Exchange:
    return ccxt.binanceusdm({"enableRateLimit": True})


def fetch_ohlcv_series(exchange: ccxt.Exchange, symbol: str, timeframe: str,
                       start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    limit = 1000
    since = int(start.timestamp() * 1000)
    all_rows = []
    while True:
        try:
            rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        except Exception as e:  # pragma: no cover
            logger.warning(f"Fetch failed for {symbol}: {e}. Using synthetic data")
            pd_freq = timeframe.replace('m', 'min')
            dates = pd.date_range(start, end, freq=pd_freq)
            price = np.cumprod(1 + np.random.normal(0, 0.001, len(dates))) * 10000
            return pd.DataFrame({"open": price, "high": price, "low": price, "close": price, "volume": 0}, index=dates)
        if not rows:
            break
        all_rows.extend(rows)
        since = rows[-1][0] + 1
        if len(rows) < limit or since > int(end.timestamp() * 1000):
            break
    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def compute_spread_and_zscore(price1: pd.Series, price2: pd.Series, method: str, window: int):
    log1 = np.log(price1)
    log2 = np.log(price2)
    if method == "cointegration":
        X = add_constant(log2)
        model = OLS(log1, X).fit()
        beta = model.params[1]
        spread = log1 - beta * log2
    else:
        beta = 1.0
        spread = log1 - log2
    rolling_mean = spread.rolling(window).mean()
    rolling_std = spread.rolling(window).std()
    zscore = (spread - rolling_mean) / rolling_std
    return spread, zscore, beta


def add_adx(df: pd.DataFrame, window: int) -> pd.Series:
    adx = ADXIndicator(df["high"], df["low"], df["close"], window=window).adx()
    return adx


# ---------------------------------------------------------------------------
# Backtesting logic
# ---------------------------------------------------------------------------


def run_backtest(cfg: dict, summary_path: str = "reports/summary.json") -> dict:
    np.random.seed(cfg.get("seed", 0))
    exchange = init_exchange()

    tz = cfg.get("timezone", "UTC")
    start = pd.Timestamp(cfg["backtest_since"], tz=tz).tz_convert("UTC")
    end = pd.Timestamp(cfg["backtest_to"], tz=tz).tz_convert("UTC")

    btc = fetch_ohlcv_series(exchange, cfg["symbols"]["btc"], cfg["timeframe"], start, end)
    eth = fetch_ohlcv_series(exchange, cfg["symbols"]["eth"], cfg["timeframe"], start, end)

    # convert timezone and filter
    btc = btc.tz_convert(tz)
    eth = eth.tz_convert(tz)
    btc = btc[(btc.index >= cfg["backtest_since"]) & (btc.index <= cfg["backtest_to"])]
    eth = eth[(eth.index >= cfg["backtest_since"]) & (eth.index <= cfg["backtest_to"])]

    data = pd.DataFrame({
        "btc_close": btc["close"],
        "btc_high": btc["high"],
        "btc_low": btc["low"],
        "eth_close": eth["close"],
        "eth_high": eth["high"],
        "eth_low": eth["low"],
    }).dropna()

    window_days = 10
    bars_per_day = int(pd.Timedelta("1D") / pd.Timedelta(cfg["timeframe"]))
    window = window_days * bars_per_day
    spread, z, beta = compute_spread_and_zscore(data["btc_close"], data["eth_close"], cfg["spread_method"], window)
    adx = add_adx(pd.DataFrame({"high": data["btc_high"], "low": data["btc_low"], "close": data["btc_close"]}), 14)

    df = pd.DataFrame({"btc": data["btc_close"], "eth": data["eth_close"], "z": z, "spread": spread, "adx": adx}).dropna()

    capital = 10000.0
    strategy_cap = capital * cfg["max_strategy_allocation"]
    risk_per_trade = capital * cfg["risk_per_trade"]
    commission = cfg["commission_pct"]
    slippage = cfg["slippage_pct"]

    position = 0
    qty_btc = qty_eth = 0.0
    entry_price_btc = entry_price_eth = 0.0
    entry_time = None

    realized = 0.0
    fees_paid = 0.0
    trade_pnls = []
    equity_curve = []
    trades = []

    for ts, row in df.iterrows():
        price_btc = row["btc"]
        price_eth = row["eth"]
        zscore = row["z"]
        adx_val = row["adx"]

        # entry
        if position == 0 and (not cfg.get("enable_regime_filter") or adx_val < cfg["adx_threshold"]):
            if zscore >= cfg["entry_z"]:
                notional = min(risk_per_trade, strategy_cap)
                qty_btc = -(notional / price_btc)
                qty_eth = (notional / price_btc) * beta * price_btc / price_eth
                entry_price_btc = price_btc * (1 - slippage)
                entry_price_eth = price_eth * (1 + slippage)
                fee = abs(entry_price_btc * qty_btc) * commission + abs(entry_price_eth * qty_eth) * commission
                fees_paid += fee
                position = -1
                entry_time = ts
                trades.append({"time": ts.isoformat(), "action": "short", "z": float(zscore), "qty_btc": qty_btc, "qty_eth": qty_eth, "fee": fee})
            elif zscore <= -cfg["entry_z"]:
                notional = min(risk_per_trade, strategy_cap)
                qty_btc = (notional / price_btc)
                qty_eth = -(notional / price_btc) * beta * price_btc / price_eth
                entry_price_btc = price_btc * (1 + slippage)
                entry_price_eth = price_eth * (1 - slippage)
                fee = abs(entry_price_btc * qty_btc) * commission + abs(entry_price_eth * qty_eth) * commission
                fees_paid += fee
                position = 1
                entry_time = ts
                trades.append({"time": ts.isoformat(), "action": "long", "z": float(zscore), "qty_btc": qty_btc, "qty_eth": qty_eth, "fee": fee})

        holding_days = (ts - entry_time).days if entry_time else 0
        if position != 0:
            unrealized = qty_btc * price_btc + qty_eth * price_eth - (qty_btc * entry_price_btc + qty_eth * entry_price_eth)
            # exits
            if abs(zscore) <= cfg["exit_z_full"] or holding_days > cfg["max_holding_days"]:
                fee = abs(price_btc * qty_btc) * commission + abs(price_eth * qty_eth) * commission
                fees_paid += fee
                realized += qty_btc * (price_btc * (1 + np.sign(qty_btc) * slippage) - entry_price_btc) + \
                            qty_eth * (price_eth * (1 + np.sign(qty_eth) * slippage) - entry_price_eth)
                realized -= fee
                trade_pnls.append(realized)
                trades.append({"time": ts.isoformat(), "action": "close", "pnl": realized})
                position = 0
                qty_btc = qty_eth = 0
                entry_time = None
            elif abs(zscore) <= cfg["exit_z_partial"]:
                close_qty_btc = qty_btc * 0.5
                close_qty_eth = qty_eth * 0.5
                fee = abs(price_btc * close_qty_btc) * commission + abs(price_eth * close_qty_eth) * commission
                fees_paid += fee
                realized += close_qty_btc * (price_btc * (1 + np.sign(close_qty_btc) * slippage) - entry_price_btc) + \
                            close_qty_eth * (price_eth * (1 + np.sign(close_qty_eth) * slippage) - entry_price_eth)
                realized -= fee
                qty_btc -= close_qty_btc
                qty_eth -= close_qty_eth
                trades.append({"time": ts.isoformat(), "action": "partial"})

        equity = capital + realized + (qty_btc * (price_btc - entry_price_btc) + qty_eth * (price_eth - entry_price_eth)) - fees_paid
        equity_curve.append(equity)

    equity_series = pd.Series(equity_curve, index=df.index)
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    mdd = float(drawdown.min()) if not drawdown.empty else 0.0

    returns = equity_series.pct_change().dropna()
    ann_factor = np.sqrt(252 * 24 * 60 / 5)
    sharpe = float((returns.mean() / returns.std()) * ann_factor) if not returns.empty else 0.0
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    pf = float(gains / abs(losses)) if losses != 0 else np.inf

    summary = {
        "total_pnl": realized,
        "trades": len([t for t in trades if t.get("action") in ("long", "short")]),
        "sharpe": sharpe,
        "profit_factor": pf,
        "mdd": mdd,
    }

    os.makedirs("reports", exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    pd.DataFrame(trades).to_csv("reports/trades.csv", index=False)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity_series.index, y=equity_series.values, name="equity"))
    fig.write_html("reports/equity_curve.html")
    dd_fig = go.Figure()
    dd_fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values, name="drawdown"))
    dd_fig.write_html("reports/drawdown.html")
    monthly = returns.resample('M').sum()
    heatmap = go.Figure(data=go.Heatmap(z=[monthly.values], x=monthly.index.strftime('%Y-%m'), y=['returns']))
    heatmap.write_html("reports/monthly_heatmap.html")

    if cfg.get("debug"):
        sample = df.head(5)
        logger.debug(sample[["spread", "z", "adx"]])

    logger.info(
        f"Total PnL {summary['total_pnl']:.2f}, Trades {summary['trades']}, Sharpe {summary['sharpe']:.2f}, PF {summary['profit_factor']:.2f}, MDD {summary['mdd']:.2f}"
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg = apply_profile(cfg, args.profile)

    if args.mode == "backtest":
        out = "reports/summary.json" if not args.profile else f"reports/summary_{args.profile}.json"
        summary = run_backtest(cfg, out)
        if args.profile:
            base = json.load(open("reports/summary.json"))
            real = summary
            compare = {"diagnostic": base, "real": real}
            with open("reports/summary_compare.json", "w") as f:
                json.dump(compare, f, indent=2)
            logger.info("Comparison saved to reports/summary_compare.json")
            print(f"Diag Sharpe {base['sharpe']:.2f} vs Real {real['sharpe']:.2f}")
            if real["sharpe"] < 1.0 or real["profit_factor"] < 1.3 or real["mdd"] < -0.2:
                suggestions = [
                    {"entry_z": cfg["entry_z"] + 0.5, "window_days": 15, "adx_threshold": cfg["adx_threshold"] + 5},
                    {"entry_z": cfg["entry_z"] - 0.5, "window_days": 20, "adx_threshold": max(5, cfg["adx_threshold"] - 5)},
                    {"entry_z": cfg["entry_z"], "window_days": 30, "adx_threshold": cfg["adx_threshold"]},
                ]
                logger.info(f"Suggestions: {suggestions}")
    else:
        logger.error("Only backtest mode implemented")


if __name__ == "__main__":
    main()

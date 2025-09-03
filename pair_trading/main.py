import os
import time
import argparse
from datetime import datetime, timedelta

import ccxt
import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv
from loguru import logger
from statsmodels.tsa.stattools import coint
from ta.trend import ADXIndicator

import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def init_exchange(cfg: dict) -> ccxt.Exchange:
    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_SECRET_KEY")
    if api_key and api_secret and not cfg.get("dry_run", True):
        exchange.apiKey = api_key
        exchange.secret = api_secret
    return exchange


# ---------------------------------------------------------------------------
# Data utilities
# ---------------------------------------------------------------------------

def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, interval: str, limit: int = 1500) -> pd.DataFrame:
    """Fetch OHLCV data and return as DataFrame."""
    raw = exchange.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def compute_spread_zscore(df_btc: pd.Series, df_eth: pd.Series, method: str, window: int):
    if method == "cointegration":
        # Engle-Granger cointegration
        score, pvalue, _ = coint(np.log(df_btc), np.log(df_eth))
        beta = np.polyfit(np.log(df_eth), np.log(df_btc), 1)[0]
        spread = np.log(df_btc) - beta * np.log(df_eth)
    else:
        beta = 1.0
        spread = np.log(df_btc / df_eth)
    zscore = (spread - spread.rolling(window).mean()) / spread.rolling(window).std()
    return spread, zscore, beta


def add_adx(df: pd.DataFrame, window: int):
    adx = ADXIndicator(df["high"], df["low"], df["close"], window).adx()
    return adx


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def backtest(cfg: dict):
    exchange = init_exchange(cfg)
    logger.info("Fetching historical data...")
    btc = fetch_ohlcv(exchange, cfg["symbols"]["btc"], cfg["interval"], cfg.get("history_limit", 1000))
    eth = fetch_ohlcv(exchange, cfg["symbols"]["eth"], cfg["interval"], cfg.get("history_limit", 1000))

    data = pd.DataFrame({"btc": btc["close"], "eth": eth["close"],
                         "btc_high": btc["high"], "btc_low": btc["low"],
                         "eth_high": eth["high"], "eth_low": eth["low"]}).dropna()

    spread, zscore, beta = compute_spread_zscore(data["btc"], data["eth"], cfg["spread_method"], cfg["window"])
    adx_btc = add_adx(btc, 14)

    df = pd.DataFrame({
        "btc": data["btc"],
        "eth": data["eth"],
        "spread": spread,
        "z": zscore,
        "adx": adx_btc
    }).dropna()

    position = 0  # 1: long spread, -1: short spread
    entry_z = cfg["z_entry"]
    half_exit = cfg["z_exit_half"]
    full_exit = cfg["z_exit_full"]
    adx_th = cfg["adx_threshold"]
    capital = cfg.get("initial_capital", 10000)
    strategy_cap = capital * cfg.get("strategy_allocation", 0.15)
    leverage = cfg.get("leverage", 2)
    fee = cfg.get("fee", 0.0004)
    slippage = cfg.get("slippage", 0.001)

    pnl = 0.0
    peak = 0.0
    mdd = 0.0
    trades = 0
    trade_logs = []

    for ts, row in df.iterrows():
        if row["adx"] >= adx_th:
            # high trend, exit any positions
            if position != 0:
                position = 0
                trade_logs.append({"time": ts, "action": "exit_adx"})
            continue

        if position == 0:
            if row["z"] <= -entry_z:
                position = 1
                entry_price_btc = row["btc"]
                entry_price_eth = row["eth"]
                trades += 1
                trade_logs.append({"time": ts, "action": "long_spread", "z": row["z"]})
            elif row["z"] >= entry_z:
                position = -1
                entry_price_btc = row["btc"]
                entry_price_eth = row["eth"]
                trades += 1
                trade_logs.append({"time": ts, "action": "short_spread", "z": row["z"]})
        elif position == 1:
            if row["z"] >= half_exit:
                position = 0.5
                trade_logs.append({"time": ts, "action": "half_exit_long"})
            if row["z"] >= full_exit:
                position = 0
                trade_pnl = (row["btc"] - entry_price_btc) - beta * (row["eth"] - entry_price_eth)
                pnl += trade_pnl
                trade_logs.append({"time": ts, "action": "full_exit_long", "pnl": trade_pnl})
        elif position == -1:
            if row["z"] <= -half_exit:
                position = -0.5
                trade_logs.append({"time": ts, "action": "half_exit_short"})
            if row["z"] <= -full_exit:
                position = 0
                trade_pnl = -(row["btc"] - entry_price_btc) + beta * (row["eth"] - entry_price_eth)
                pnl += trade_pnl
                trade_logs.append({"time": ts, "action": "full_exit_short", "pnl": trade_pnl})

        equity = pnl * leverage - abs(pnl) * (fee + slippage)
        peak = max(peak, equity)
        if peak > 0:
            mdd = min(mdd, (equity - peak) / peak)
        if mdd <= cfg.get("kill_switch_mdd", -0.05):
            logger.warning("Kill switch triggered due to MDD.")
            break

    if trades == 0:
        sharpe = 0
        profit_factor = 0
    else:
        returns = pd.Series([log["pnl"] for log in trade_logs if "pnl" in log])
        sharpe = (returns.mean() / returns.std()) * np.sqrt(365 * 24 * 12) if not returns.empty else 0
        profit_factor = returns[returns > 0].sum() / abs(returns[returns < 0].sum()) if not returns.empty else 0

    summary = {
        "total_pnl": pnl,
        "mdd": mdd,
        "trades": trades,
        "sharpe": sharpe,
        "profit_factor": profit_factor
    }

    os.makedirs("reports", exist_ok=True)
    pd.Series(summary).to_csv("reports/backtest_summary.csv")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=spread, name="spread"))
    fig.write_html("reports/equity_curve.html")
    return summary


# ---------------------------------------------------------------------------
# Live trading stub
# ---------------------------------------------------------------------------

def run_live(cfg: dict):
    exchange = init_exchange(cfg)
    logger.info("Starting live trading in %s mode", "dry-run" if cfg.get("dry_run", True) else "live")
    while True:
        try:
            btc = fetch_ohlcv(exchange, cfg["symbols"]["btc"], cfg["interval"], limit=cfg.get("live_limit", 200))
            eth = fetch_ohlcv(exchange, cfg["symbols"]["eth"], cfg["interval"], limit=cfg.get("live_limit", 200))
            spread, zscore, beta = compute_spread_zscore(btc["close"], eth["close"], cfg["spread_method"], cfg["window"])
            adx = add_adx(btc, 14)
            z = zscore.iloc[-1]
            adx_last = adx.iloc[-1]
            logger.info(f"Latest z={z:.2f}, ADX={adx_last:.2f}")
            # Decision logic would be similar to backtest. For brevity, we omit.
        except Exception as e:
            logger.error(f"Live loop error: {e}")
        time.sleep(cfg.get("live_sleep", 60))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["backtest", "live"], required=True)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    load_dotenv()
    cfg = load_config(args.config)

    if args.mode == "backtest":
        summary = backtest(cfg)
        logger.info(f"Backtest summary: {summary}")
    else:
        run_live(cfg)


if __name__ == "__main__":
    main()

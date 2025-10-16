"""Utility functions for fetching market data from Binance using ccxt."""
from __future__ import annotations

import os
from typing import Dict, Iterable, Optional

import ccxt
import pandas as pd

BINANCE_API_KEY_ENV = "BINANCE_API_KEY"
BINANCE_API_SECRET_ENV = "BINANCE_API_SECRET"


def _create_binance_client() -> ccxt.binance:
    """Instantiate a ccxt Binance client using environment variables if available."""
    api_key = os.getenv(BINANCE_API_KEY_ENV)
    api_secret = os.getenv(BINANCE_API_SECRET_ENV)

    client_config = {"enableRateLimit": True}
    if api_key and api_secret:
        client_config.update({"apiKey": api_key, "secret": api_secret})

    return ccxt.binance(client_config)


def create_binance_client() -> ccxt.binance:
    """Public wrapper to instantiate a Binance client with environment credentials."""

    return _create_binance_client()


def fetch_recent_ohlcv(
    symbol: str,
    timeframe: str = "15m",
    limit: int = 500,
    client: Optional[ccxt.binance] = None,
) -> pd.DataFrame:
    """Fetch recent OHLCV data for a given symbol and return a cleaned DataFrame."""
    client = client or _create_binance_client()

    try:
        ohlcv = client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except ccxt.NetworkError as exc:  # pragma: no cover - requires network failure
        raise RuntimeError(
            "Network error while fetching data from Binance. "
            "Check your internet connection, VPN/proxy, or Binance API status."
        ) from exc
    except ccxt.BaseError as exc:  # pragma: no cover - requires API failure
        raise RuntimeError(
            f"Binance API returned an error for {symbol} {timeframe} data: {exc}"
        ) from exc

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = (
        df.drop_duplicates(subset="timestamp")
        .set_index("timestamp")
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
    )

    return df


def fetch_btc_eth_15m(
    client: Optional[ccxt.binance] = None, limit: int = 500
) -> Dict[str, pd.DataFrame]:
    """Convenience helper to fetch recent 15m data for BTCUSDT and ETHUSDT."""
    client = client or _create_binance_client()
    symbols = {
        "BTCUSDT": "BTC/USDT",
        "ETHUSDT": "ETH/USDT",
    }

    return {
        symbol_alias: fetch_recent_ohlcv(symbol, timeframe="15m", limit=limit, client=client)
        for symbol_alias, symbol in symbols.items()
    }


def fetch_timeframes(
    symbols: Dict[str, str],
    timeframes: Iterable[str],
    *,
    limit: int = 240,
    client: Optional[ccxt.binance] = None,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Fetch OHLCV data for multiple symbols and timeframes in a single call."""

    client = client or _create_binance_client()
    results: Dict[str, Dict[str, pd.DataFrame]] = {}
    for timeframe in timeframes:
        frame_results: Dict[str, pd.DataFrame] = {}
        for alias, market in symbols.items():
            frame_results[alias] = fetch_recent_ohlcv(
                market,
                timeframe=str(timeframe),
                limit=limit,
                client=client,
            )
        results[str(timeframe)] = frame_results
    return results


def fetch_latest_price(
    market: str,
    *,
    client: Optional[ccxt.binance] = None,
) -> float:
    """Fetch the latest traded price for the given market."""

    client = client or _create_binance_client()
    try:
        ticker = client.fetch_ticker(market)
    except ccxt.BaseError as exc:  # pragma: no cover - network/API failure
        raise RuntimeError(f"Failed to fetch ticker for {market}: {exc}") from exc
    price = ticker.get("last") or ticker.get("close")
    if price is None:
        raise RuntimeError(f"Ticker for {market} does not include a last price: {ticker}")
    return float(price)


__all__ = [
    "create_binance_client",
    "fetch_recent_ohlcv",
    "fetch_btc_eth_15m",
    "fetch_timeframes",
    "fetch_latest_price",
]


if __name__ == "__main__":
    data = fetch_btc_eth_15m()
    for pair, df in data.items():
        print(f"{pair}: {len(df)} rows fetched, last timestamp = {df.index[-1] if not df.empty else 'N/A'}")

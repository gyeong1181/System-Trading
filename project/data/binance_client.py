"""Utilities for fetching Binance spot candlestick data."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import ccxt
import pandas as pd
from dotenv import load_dotenv

BINANCE_API_KEY_ENV = "BINANCE_API_KEY"
BINANCE_API_SECRET_ENV = "BINANCE_API_SECRET"

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class BinanceClient:
    """Small helper around :mod:`ccxt` for OHLCV retrieval."""

    timeframe: str = "15m"
    limit: int = 500
    client: Optional[ccxt.binance] = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = self._create_client()

    def _create_client(self) -> ccxt.binance:
        api_key = os.getenv(BINANCE_API_KEY_ENV)
        api_secret = os.getenv(BINANCE_API_SECRET_ENV)

        client_config = {"enableRateLimit": True}
        if api_key and api_secret:
            client_config.update({"apiKey": api_key, "secret": api_secret})
        else:
            logger.info("Using public Binance endpoints (no API key provided).")

        return ccxt.binance(client_config)

    def fetch_ohlcv(
        self, symbol: str, *, timeframe: Optional[str] = None, limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Return cleaned OHLCV candles for ``symbol``."""

        tf = timeframe or self.timeframe
        lm = limit or self.limit

        try:
            raw = self.client.fetch_ohlcv(symbol, timeframe=tf, limit=lm)
        except ccxt.NetworkError as exc:  # pragma: no cover - network failure requires integration
            raise RuntimeError(
                "Network error while fetching data from Binance. "
                "Check VPN/firewall settings or retry shortly."
            ) from exc
        except ccxt.BaseError as exc:  # pragma: no cover - depends on exchange state
            raise RuntimeError(f"Binance API error for {symbol} {tf}: {exc}") from exc

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = (
            df.drop_duplicates(subset="timestamp")
            .set_index("timestamp")
            .sort_index()
            .apply(pd.to_numeric, errors="coerce")
            .dropna()
        )
        return df

    def fetch_many(self, symbols: Iterable[str]) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV candles for every item in ``symbols``."""

        return {symbol: self.fetch_ohlcv(symbol) for symbol in symbols}


DEFAULT_SYMBOLS = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
}


def fetch_btc_eth_15m(limit: int = 500) -> Dict[str, pd.DataFrame]:
    """Convenience wrapper used by notebooks and scripts."""

    client = BinanceClient(timeframe="15m", limit=limit)
    data = {}
    for alias, ccxt_symbol in DEFAULT_SYMBOLS.items():
        data[alias] = client.fetch_ohlcv(ccxt_symbol)
    return data


__all__ = ["BinanceClient", "fetch_btc_eth_15m"]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    logging.basicConfig(level=logging.INFO)
    frames = fetch_btc_eth_15m()
    for symbol, frame in frames.items():
        logger.info(
            "%s -> %s rows (%s - %s)", symbol, len(frame), frame.index.min(), frame.index.max()
        )

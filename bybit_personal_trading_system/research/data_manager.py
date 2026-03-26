from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from src.config import Settings


BYBIT_PUBLIC_BASE = "https://api.bybit.com"


def interval_to_minutes(interval: str) -> int:
    value = str(interval)
    if value in {"D", "1d", "1D", "d"}:
        return 1440
    if value.endswith("m"):
        return int(value[:-1])
    if value.endswith("h"):
        return int(value[:-1]) * 60
    return int(value)


@dataclass
class PublicMarketClient:
    base_url: str = BYBIT_PUBLIC_BASE

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(params)
        url = f"{self.base_url}{path}?{query}"
        try:
            with urlopen(url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Bybit 공용 API 호출에 실패했습니다: {exc}") from exc
        if payload.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit 응답 오류: {payload.get('retMsg')}")
        return payload

    def fetch_ohlcv(self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int) -> pd.DataFrame:
        payload = self._get(
            "/v5/market/kline",
            {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "start": start_ms,
                "end": end_ms,
                "limit": limit,
            },
        )
        rows = payload["result"]["list"]
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "turnover"])
        frame = pd.DataFrame(rows, columns=["start_time", "open", "high", "low", "close", "volume", "turnover"])
        frame["timestamp"] = pd.to_datetime(frame["start_time"].astype("int64"), unit="ms", utc=True).dt.tz_convert(None)
        numeric = ["open", "high", "low", "close", "volume", "turnover"]
        for column in numeric:
            frame[column] = frame[column].astype(float)
        frame = frame.sort_values("timestamp").drop_duplicates("timestamp")
        return frame.set_index("timestamp")[numeric]

    def fetch_funding(self, symbol: str, start_ms: int, end_ms: int, limit: int) -> pd.DataFrame:
        payload = self._get(
            "/v5/market/funding/history",
            {
                "category": "linear",
                "symbol": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
        )
        rows = payload["result"]["list"]
        if not rows:
            return pd.DataFrame(columns=["funding_rate"])
        frame = pd.DataFrame(rows)
        frame["timestamp"] = pd.to_datetime(frame["fundingRateTimestamp"].astype("int64"), unit="ms", utc=True).dt.tz_convert(None)
        frame["funding_rate"] = frame["fundingRate"].astype(float)
        frame = frame.sort_values("timestamp").drop_duplicates("timestamp")
        return frame.set_index("timestamp")[["funding_rate"]]


class MarketDataManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = PublicMarketClient()
        self.settings.market_dir.mkdir(parents=True, exist_ok=True)

    def _ohlcv_paths(self, symbol: str, interval: str) -> tuple[Path, Path]:
        base = f"{symbol}_{interval}"
        return self.settings.market_dir / f"{base}.parquet", self.settings.market_dir / f"{base}.csv"

    def _funding_paths(self, symbol: str) -> tuple[Path, Path]:
        return self.settings.market_dir / f"{symbol}_funding.parquet", self.settings.market_dir / f"{symbol}_funding.csv"

    def _save_frame(self, frame: pd.DataFrame, parquet_path: Path, csv_path: Path) -> None:
        if bool(self.settings.data["save_parquet"]):
            frame.to_parquet(parquet_path)
        if bool(self.settings.data["save_csv"]):
            frame.to_csv(csv_path, encoding="utf-8")

    def _load_saved_frame(self, parquet_path: Path, csv_path: Path) -> pd.DataFrame:
        if parquet_path.exists():
            frame = pd.read_parquet(parquet_path)
        elif csv_path.exists():
            frame = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        else:
            frame = pd.DataFrame()
        if not frame.empty:
            frame.index = pd.to_datetime(frame.index)
        return frame

    def validate_gaps(self, frame: pd.DataFrame, interval: str) -> dict[str, Any]:
        if frame.empty:
            return {"missing_bars": 0, "expected_bars": 0}
        expected = pd.date_range(frame.index.min(), frame.index.max(), freq=f"{interval_to_minutes(interval)}min")
        missing = expected.difference(frame.index)
        return {"missing_bars": int(len(missing)), "expected_bars": int(len(expected))}

    def _merge_frames(self, left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
        if left.empty:
            return right
        if right.empty:
            return left
        merged = pd.concat([left, right]).sort_index()
        return merged[~merged.index.duplicated(keep="last")]

    def update_market_data(self, symbol: str, interval: str) -> dict[str, Any]:
        minutes = interval_to_minutes(interval)
        now = datetime.now(UTC)
        start = now - timedelta(days=int(self.settings.data["history_days"]))
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(now.timestamp() * 1000)
        limit = int(self.settings.data["fetch_limit"])
        interval_ms = minutes * 60 * 1000

        parquet_path, csv_path = self._ohlcv_paths(symbol, interval)
        funding_parquet, funding_csv = self._funding_paths(symbol)

        ohlcv_existing = self._load_saved_frame(parquet_path, csv_path)
        funding_existing = self._load_saved_frame(funding_parquet, funding_csv)

        ohlcv_parts: list[pd.DataFrame] = []
        cursor = start_ms
        while cursor < end_ms:
            chunk_end = min(end_ms, cursor + interval_ms * limit)
            batch = self.client.fetch_ohlcv(symbol, interval, cursor, chunk_end, limit)
            if batch.empty:
                cursor = chunk_end + interval_ms
                continue
            ohlcv_parts.append(batch)
            cursor = int(batch.index.max().timestamp() * 1000) + interval_ms

        funding_parts: list[pd.DataFrame] = []
        funding_cursor = start_ms
        funding_step = 8 * 60 * 60 * 1000 * limit
        while funding_cursor < end_ms:
            chunk_end = min(end_ms, funding_cursor + funding_step)
            batch = self.client.fetch_funding(symbol, funding_cursor, chunk_end, limit)
            if batch.empty:
                funding_cursor = chunk_end + 1
                continue
            funding_parts.append(batch)
            funding_cursor = int(batch.index.max().timestamp() * 1000) + 1

        ohlcv = self._merge_frames(ohlcv_existing, pd.concat(ohlcv_parts) if ohlcv_parts else pd.DataFrame())
        funding = self._merge_frames(funding_existing, pd.concat(funding_parts) if funding_parts else pd.DataFrame())
        if ohlcv.empty:
            raise RuntimeError(f"{symbol} {interval} 시장 데이터를 가져오지 못했습니다.")

        self._save_frame(ohlcv, parquet_path, csv_path)
        self._save_frame(funding, funding_parquet, funding_csv)

        merged = ohlcv.join(funding.reindex(ohlcv.index).fillna(0.0), how="left")
        merged["symbol"] = symbol
        return {"frame": merged, "validation": self.validate_gaps(ohlcv, interval)}

    def load_market_data(self, symbol: str, interval: str) -> pd.DataFrame:
        parquet_path, csv_path = self._ohlcv_paths(symbol, interval)
        funding_parquet, funding_csv = self._funding_paths(symbol)
        ohlcv = self._load_saved_frame(parquet_path, csv_path)
        funding = self._load_saved_frame(funding_parquet, funding_csv)
        if ohlcv.empty:
            raise FileNotFoundError(f"{symbol} {interval} 데이터 파일이 없습니다. 먼저 data-fetch를 실행하세요.")
        merged = ohlcv.join(funding.reindex(ohlcv.index).fillna(0.0), how="left")
        merged["symbol"] = symbol
        return merged

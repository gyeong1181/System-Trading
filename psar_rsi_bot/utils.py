import asyncio
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional


LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_env(env_path: Optional[str] = None) -> Dict[str, str]:
    """
    Load key/value pairs from a dotenv style file and merge them with os.environ.
    Environment variables take precedence over file values.
    """
    env_file = Path(env_path) if env_path else Path(__file__).resolve().parents[1] / ".env"
    values: Dict[str, str] = {}
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    # overlay system env vars
    for key, value in os.environ.items():
        values[key] = value
    return values


def get_logger(name: str = "BTCTrendFollower", level: int = logging.INFO, log_to_file: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_to_file:
        log_file = LOG_DIR / "psar_rsi_bot.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


async def backoff_retry(
    task_fn: Callable[[], Awaitable[Any]],
    logger: logging.Logger,
    max_retries: int = 5,
    base_delay: float = 3.0,
) -> Any:
    """
    Execute an async callable with exponential backoff.
    """
    attempt = 0
    while True:
        try:
            return await task_fn()
        except Exception as exc:  # pragma: no cover - defensive
            attempt += 1
            if max_retries != -1 and attempt > max_retries:
                logger.exception("backoff_retry exceeded retries: %s", exc)
                raise
            sleep_for = base_delay * (2 ** (attempt - 1))
            sleep_for *= random.uniform(0.8, 1.2)
            sleep_for = min(sleep_for, 60)
            logger.warning("Task failed (%s). Retrying in %.2fs", exc, sleep_for)
            await asyncio.sleep(sleep_for)


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool

    @classmethod
    def from_binance_ws(cls, payload: Dict[str, Any]) -> "Candle":
        kline = payload["k"]
        return cls(
            timestamp=int(kline["t"]),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            closed=bool(kline["x"]),
        )

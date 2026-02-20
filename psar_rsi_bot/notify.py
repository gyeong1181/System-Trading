from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from prometheus_client import Counter

from utils import get_app_logger

TELEGRAM_SEND_TOTAL = Counter(
    "telegram_send_total",
    "Total Telegram send attempts",
)
TELEGRAM_SEND_FAIL_TOTAL = Counter(
    "telegram_send_fail_total",
    "Total Telegram send failures",
    ["reason"],
)


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.app_logger = get_app_logger()

    async def send(self, message: str) -> None:
        TELEGRAM_SEND_TOTAL.inc()
        if not self.bot_token or not self.chat_id:
            self.app_logger.warning("telegram_disabled missing_token_or_chat")
            TELEGRAM_SEND_FAIL_TOTAL.labels("disabled").inc()
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, data=payload)
                if resp.status_code >= 300:
                    self.app_logger.error(
                        "telegram_error status=%s body=%s", resp.status_code, resp.text
                    )
                    TELEGRAM_SEND_FAIL_TOTAL.labels("http_error").inc()
        except Exception as exc:
            # do not crash the main flow on notify errors
            self.app_logger.error("telegram_exception %s", exc)
            TELEGRAM_SEND_FAIL_TOTAL.labels("exception").inc()
            await asyncio.sleep(0)

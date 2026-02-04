from __future__ import annotations

import asyncio
from typing import Optional

import httpx


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, data=payload)
        except Exception:
            # do not crash the main flow on notify errors
            await asyncio.sleep(0)

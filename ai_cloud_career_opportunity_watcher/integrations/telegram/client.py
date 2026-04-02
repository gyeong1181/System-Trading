from __future__ import annotations

import httpx

from app.config import Settings


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_message(self, text: str) -> dict:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            raise RuntimeError("Telegram 설정이 비어 있습니다. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 확인하세요.")

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        response = httpx.post(
            url,
            timeout=self.settings.request_timeout_seconds,
            json={
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        return response.json()

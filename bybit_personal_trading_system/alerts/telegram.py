from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.config import Settings
from src.models import ExecutionOrder


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.allowed_commands = {"/status", "/pause", "/resume", "/kill"}
        self.settings.telegram_offset_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(
            self.settings.telegram.get("enabled")
            and self.settings.telegram_bot_token
            and self.settings.telegram_chat_id
        )

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False}
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/{method}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError:
            return {"ok": False}

    def send_message(self, text: str) -> None:
        if not self.enabled:
            return
        self._request(
            "sendMessage",
            {"chat_id": self.settings.telegram_chat_id, "text": text},
        )

    def send_trade_alert(self, order: ExecutionOrder, status: str, pnl: float | None = None) -> None:
        action_ko = "진입" if order.action == "open" else "청산"
        side_ko = "롱" if order.side == "long" else "숏"
        lines = [
            f"[{order.mode.upper()}] {action_ko} 알림",
            f"전략: {order.strategy_id}",
            f"심볼: {order.symbol}",
            f"방향: {side_ko}",
            f"수량: {order.qty}",
            f"상태: {status}",
        ]
        if pnl is not None:
            lines.append(f"실현손익: {pnl:.2f} USDT")
        self.send_message("\n".join(lines))

    def send_error_alert(self, message: str) -> None:
        self.send_message(f"[오류]\n{message}")

    def send_daily_summary(self, pnl: float, trades: int, win_rate: float) -> None:
        self.send_message(
            f"[일일 요약]\n실현손익: {pnl:.2f} USDT\n거래 수: {trades}건\n승률: {win_rate * 100:.1f}%"
        )

    def send_monthly_summary(self, pnl: float, trades: int, win_rate: float) -> None:
        self.send_message(
            f"[월간 요약]\n실현손익: {pnl:.2f} USDT\n거래 수: {trades}건\n승률: {win_rate * 100:.1f}%"
        )

    def _load_offset(self) -> int:
        path = self.settings.telegram_offset_path
        if not path.exists():
            return 0
        try:
            return int(path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return 0

    def _save_offset(self, value: int) -> None:
        self.settings.telegram_offset_path.write_text(str(value), encoding="utf-8")

    def poll_commands(self, stop_event: threading.Event, handler: Callable[[str], str]) -> None:
        if not self.enabled:
            return
        offset = self._load_offset()
        while not stop_event.is_set():
            payload = {
                "offset": offset + 1,
                "timeout": 25,
                "allowed_updates": ["message"],
            }
            response = self._request("getUpdates", payload)
            if not response.get("ok"):
                continue
            for update in response.get("result", []):
                offset = max(offset, int(update.get("update_id", 0)))
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                if chat_id != self.settings.telegram_chat_id:
                    continue
                text = str(message.get("text", "")).strip()
                if text not in self.allowed_commands:
                    continue
                reply = handler(text)
                if reply:
                    self.send_message(reply)
            self._save_offset(offset)

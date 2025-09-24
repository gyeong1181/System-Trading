"""Tests for the Telegram notifier helper."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

import asyncio

from telegram.error import TelegramError

from project.alerts.telegram_bot import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_send_trade_alert_awaits_bot_send_message(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()

            notifier = TelegramNotifier(bot_token="token", chat_id="chat")
            notifier.send_trade_alert("hello")

            bot_instance.send_message.assert_awaited_once()
            self.assertEqual(
                bot_instance.send_message.await_args.kwargs,
                {"chat_id": "chat", "text": "hello", "parse_mode": None, "disable_notification": False},
            )

    def test_send_trade_alert_handles_running_loop_error(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()

            def fake_background_runner(coro_factory):
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(coro_factory())
                finally:
                    loop.close()

            background_runner = Mock(side_effect=fake_background_runner)

            def fake_asyncio_run(coro):
                coro.close()
                raise RuntimeError("asyncio.run() cannot be called from a running event loop")

            with patch("project.alerts.telegram_bot.asyncio.run", new=fake_asyncio_run), patch.object(
                TelegramNotifier, "_run_in_background_loop", new=background_runner
            ):
                notifier = TelegramNotifier(bot_token="token", chat_id="chat")
                notifier.send_trade_alert("hello")

            background_runner.assert_called_once()
            bot_instance.send_message.assert_awaited_once()

    def test_send_trade_alert_logs_telegram_error(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls, self.assertLogs(
            "project.alerts.telegram_bot", level="ERROR"
        ) as log_ctx:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock(side_effect=TelegramError("boom"))

            notifier = TelegramNotifier(bot_token="token", chat_id="chat")
            notifier.send_trade_alert("hello")

        self.assertTrue(log_ctx.output)
        self.assertIn("Failed to send Telegram trade alert.", log_ctx.output[0])


if __name__ == "__main__":
    unittest.main()

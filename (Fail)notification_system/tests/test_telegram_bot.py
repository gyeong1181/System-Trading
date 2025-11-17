"""Tests for the Telegram notifier helper."""
from __future__ import annotations

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import TelegramError

from project.alerts.telegram_bot import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_send_trade_alert_awaits_bot_send_message(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()
            bot_instance.send_document = AsyncMock()

            notifier = TelegramNotifier(bot_token="token", chat_id="chat")
            notifier.send_trade_alert("hello")

            bot_instance.send_message.assert_awaited_once()
            self.assertEqual(
                bot_instance.send_message.await_args.kwargs,
                {"chat_id": "chat", "text": "hello", "parse_mode": None, "disable_notification": False},
            )
            bot_instance.send_document.assert_not_awaited()

    def test_send_trade_alert_logs_telegram_error(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls, self.assertLogs(
            "project.alerts.telegram_bot", level="ERROR"
        ) as log_ctx:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock(side_effect=TelegramError("boom"))
            bot_instance.send_document = AsyncMock()

            notifier = TelegramNotifier(bot_token="token", chat_id="chat")
            notifier.send_trade_alert("hello")

        self.assertTrue(log_ctx.output)
        self.assertIn("Failed to send Telegram trade alert.", log_ctx.output[0])

    def test_send_trade_alert_dispatches_attachments(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()
            bot_instance.send_document = AsyncMock()

            with patch("pathlib.Path.exists", return_value=True), patch(
                "pathlib.Path.open"
            ) as open_mock:
                open_mock.return_value.__enter__.return_value = "file-handle"
                notifier = TelegramNotifier(bot_token="token", chat_id="chat")
            notifier.send_trade_alert("hello", attachments=["/tmp/report.png"])

        bot_instance.send_message.assert_awaited_once()
        bot_instance.send_document.assert_awaited_once()

    def test_send_trade_alert_uses_existing_event_loop(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()
            mock_loop = MagicMock()
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_loop.create_task.return_value = mock_task
            with patch("asyncio.get_running_loop", return_value=mock_loop):
                notifier = TelegramNotifier(bot_token="token", chat_id="chat")
                notifier.send_trade_alert("hello")

        mock_loop.create_task.assert_called_once()
        mock_task.add_done_callback.assert_called_once()

    def test_send_trade_alert_suppresses_cancelled_error(self) -> None:
        with patch("project.alerts.telegram_bot.Bot") as bot_cls:
            bot_instance = bot_cls.return_value
            bot_instance.send_message = AsyncMock()
            mock_loop = MagicMock()
            mock_task = MagicMock()

            def _trigger_callback(cb):
                cb(mock_task)

            mock_task.add_done_callback = MagicMock(side_effect=_trigger_callback)
            mock_task.result.side_effect = asyncio.CancelledError()
            mock_loop.create_task.return_value = mock_task
            with patch("asyncio.get_running_loop", return_value=mock_loop), patch(
                "project.alerts.telegram_bot.logger"
            ) as logger_mock:
                notifier = TelegramNotifier(bot_token="token", chat_id="chat")
                notifier.send_trade_alert("hello")

            logger_mock.debug.assert_called_once()


if __name__ == "__main__":
    unittest.main()

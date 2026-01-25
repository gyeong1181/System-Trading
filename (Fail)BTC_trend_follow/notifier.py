"""
Telegram 알림 모듈
거래 신호, 손익, 에러 등을 Telegram으로 실시간 알림
"""

from __future__ import annotations

import logging
import os
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


class TelegramNotifier:
    """Telegram 봇을 통한 알림 전송 클래스"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        초기화
        
        Args:
            bot_token: Telegram Bot Token (환경변수 TELEGRAM_BOT_TOKEN에서도 읽음)
            chat_id: Telegram Chat ID (환경변수 TELEGRAM_CHAT_ID에서도 읽음)
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.logger = logging.getLogger("TelegramNotifier")
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            self.logger.warning("Telegram 알림이 비활성화되었습니다. BOT_TOKEN과 CHAT_ID를 설정하세요.")
        elif requests is None:
            self.logger.error("requests 패키지가 설치되지 않았습니다. pip install requests")
            self.enabled = False
        else:
            self.logger.info("Telegram 알림이 활성화되었습니다.")

    def _send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Telegram으로 메시지 전송 (내부 함수)
        
        Args:
            message: 전송할 메시지
            parse_mode: 메시지 포맷 (HTML 또는 Markdown)
        
        Returns:
            전송 성공 여부
        """
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Telegram 메시지 전송 실패: {e}")
            return False

    def notify_entry(self, symbol: str, side: str, qty: float, price: float, mode: str = "PAPER"):
        """
        매수/매도 진입 알림
        
        Args:
            symbol: 거래 심볼 (예: BTCUSDT)
            side: 포지션 방향 (long 또는 short)
            qty: 수량
            price: 진입 가격
            mode: 모드 (PAPER 또는 LIVE)
        """
        emoji = "🟢" if side.lower() == "long" else "🔴"
        mode_text = "📄 페이퍼" if mode == "PAPER" else "💰 실거래"
        message = f"""
{emoji} <b>포지션 진입</b>

모드: {mode_text}
심볼: {symbol}
방향: {side.upper()}
수량: {qty:.6f}
가격: ${price:,.2f}
"""
        self._send_message(message.strip())

    def notify_exit(self, symbol: str, side: str, qty: float, price: float, pnl: float, reason: str, mode: str = "PAPER"):
        """
        포지션 청산 알림
        
        Args:
            symbol: 거래 심볼
            side: 포지션 방향
            qty: 수량
            price: 청산 가격
            pnl: 손익 (양수=수익, 음수=손실)
            reason: 청산 사유
            mode: 모드
        """
        emoji = "✅" if pnl >= 0 else "❌"
        mode_text = "📄 페이퍼" if mode == "PAPER" else "💰 실거래"
        pnl_text = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        
        message = f"""
{emoji} <b>포지션 청산</b>

모드: {mode_text}
심볼: {symbol}
방향: {side.upper()}
수량: {qty:.6f}
가격: ${price:,.2f}
손익: {pnl_text}
사유: {reason}
"""
        self._send_message(message.strip())

    def notify_error(self, error_message: str):
        """
        에러 알림
        
        Args:
            error_message: 에러 메시지
        """
        message = f"""
⚠️ <b>에러 발생</b>

{error_message}
"""
        self._send_message(message.strip())

    def notify_info(self, info_message: str):
        """
        정보 알림
        
        Args:
            info_message: 정보 메시지
        """
        message = f"""
ℹ️ <b>정보</b>

{info_message}
"""
        self._send_message(message.strip())

    def notify_equity(self, equity: float, mode: str = "PAPER"):
        """
        자산 현황 알림 (주기적)
        
        Args:
            equity: 현재 자산
            mode: 모드
        """
        mode_text = "📄 페이퍼" if mode == "PAPER" else "💰 실거래"
        message = f"""
📊 <b>자산 현황</b>

모드: {mode_text}
자산: ${equity:,.2f}
"""
        self._send_message(message.strip())


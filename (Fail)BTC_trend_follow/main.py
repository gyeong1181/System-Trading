"""
Docker 기반 메인 실행 파일
Telegram 알림, S3 백업, CloudWatch 로그가 통합된 버전
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

import pandas as pd

from btc_trend_follow import BTCTrendFollower, StrategyConfig
from exchange import (
    BinanceCandleStream,
    BinanceLiveExchange,
    BinanceRestClient,
    ExchangeClient,
    PaperExchangeClient,
)
from logger import setup_cloudwatch_logger
from notifier import TelegramNotifier
from reports import TradeReporter
from storage import S3Storage
from utils import Candle, load_env


class TradingBot:
    """통합 자동매매 봇 클래스"""

    def __init__(self):
        """초기화"""
        # 환경변수 로드
        self.env = load_env()
        
        # CloudWatch 로거 설정
        self.logger = setup_cloudwatch_logger(
            logger_name="BTCTrendFollower",
            log_group_name=self.env.get("CLOUDWATCH_LOG_GROUP"),
        )
        
        # Telegram 알림 초기화
        self.notifier = TelegramNotifier()
        
        # S3 백업 초기화
        self.s3_storage = S3Storage()
        
        # 전략 설정
        self.config = self._load_config()
        
        # 리포트 생성
        self.reporter = TradeReporter()
        
        # 거래소 클라이언트 초기화
        self.exchange = self._create_exchange()
        
        # 봇 초기화
        self.bot = BTCTrendFollower(self.config, self.exchange)
        
        # 종료 신호 처리
        self._setup_signal_handlers()

    def _load_config(self) -> StrategyConfig:
        """환경변수에서 전략 설정 로드"""
        symbol = self.env.get("BTC_TREND_SYMBOL") or self.env.get("AURABOT_SYMBOL", "BTCUSDT")
        interval = self.env.get("BTC_TREND_INTERVAL") or self.env.get("AURABOT_INTERVAL", "4h")
        risk_pct = float(self.env.get("BTC_TREND_RISK_PCT") or self.env.get("AURABOT_RISK_PCT", "1.0"))
        leverage = float(self.env.get("BTC_TREND_LEVERAGE") or self.env.get("AURABOT_LEVERAGE", "1.0"))
        use_short_env = (self.env.get("BTC_TREND_USE_SHORT") or self.env.get("AURABOT_USE_SHORT", "false")).lower()
        use_short = use_short_env in ("1", "true", "yes", "on")
        
        return StrategyConfig(
            symbol=symbol,
            interval=interval,
            risk_pct=risk_pct,
            leverage=leverage,
            use_short=use_short,
        )

    def _create_exchange(self) -> ExchangeClient:
        """거래소 클라이언트 생성"""
        env_paper = self.env.get("BTC_TREND_PAPER_MODE") or self.env.get("AURABOT_PAPER_MODE", "true")
        paper_mode = env_paper.lower() not in ("0", "false", "no", "off")
        
        if paper_mode:
            starting_equity = float(self.env.get("PAPER_STARTING_EQUITY", "10000.0"))
            self.logger.info(f"페이퍼 모드로 시작합니다. 초기 자산: ${starting_equity:,.2f}")
            return PaperExchangeClient(
                starting_equity=starting_equity,
                reporter=self.reporter,
                notifier=self.notifier,
            )
        else:
            api_key = self.env.get("BINANCE_API_KEY") or self.env.get("API_KEY")
            api_secret = self.env.get("BINANCE_API_SECRET") or self.env.get("SECRET_KEY")
            if not api_key or not api_secret:
                raise RuntimeError("실거래 모드에서는 BINANCE_API_KEY와 BINANCE_API_SECRET이 필요합니다.")
            self.logger.warning("⚠️ 실거래 모드로 시작합니다!")
            if self.notifier.enabled:
                self.notifier.notify_info("실거래 모드로 봇이 시작되었습니다.")
            return BinanceLiveExchange(
                api_key=api_key,
                api_secret=api_secret,
                reporter=self.reporter,
                notifier=self.notifier,
            )

    def _setup_signal_handlers(self):
        """종료 신호 처리 설정"""
        def signal_handler(sig, frame):
            self.logger.info("종료 신호를 받았습니다. 정리 중...")
            if self.notifier.enabled:
                self.notifier.notify_info("봇이 종료됩니다.")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _periodic_backup(self, interval_seconds: int = 3600):
        """주기적 S3 백업 (기본 1시간마다)"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                self.logger.info("주기적 S3 백업 시작...")
                self.s3_storage.backup_reports("reports")
                self.logger.info("S3 백업 완료")
            except Exception as e:
                self.logger.error(f"S3 백업 중 오류: {e}")

    async def _periodic_equity_notification(self, interval_seconds: int = 86400):
        """주기적 자산 알림 (기본 24시간마다)"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                equity = await self.exchange.fetch_equity()
                mode = getattr(self.exchange, "mode_name", "PAPER")
                if self.notifier.enabled:
                    self.notifier.notify_equity(equity, mode)
            except Exception as e:
                self.logger.error(f"자산 알림 중 오류: {e}")

    async def run(self):
        """메인 실행 루프"""
        try:
            # 시작 알림
            if self.notifier.enabled:
                mode = getattr(self.exchange, "mode_name", "PAPER")
                self.notifier.notify_info(
                    f"봇이 시작되었습니다.\n"
                    f"모드: {mode}\n"
                    f"심볼: {self.config.symbol}\n"
                    f"인터벌: {self.config.interval}\n"
                    f"레버리지: {self.config.leverage}x"
                )
            
            # 과거 데이터 로드 (웜업)
            self.logger.info("과거 데이터 로드 중...")
            await self.bot.warmup_with_rest(bars=500)
            
            # 백그라운드 작업 시작
            backup_task = asyncio.create_task(self._periodic_backup())
            equity_task = asyncio.create_task(self._periodic_equity_notification())
            
            # 실시간 거래 시작
            self.logger.info("실시간 거래 모드 시작...")
            stream = BinanceCandleStream(self.config.symbol, self.config.interval, logger=self.bot.logger)
            
            async def handle_candle(candle: Candle):
                await self.bot.handle_candle(candle)
                # 거래 후 즉시 백업 (선택사항)
                # await asyncio.sleep(1)  # 백업은 주기적으로만
            
            await stream.start(handle_candle)
            
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 중단되었습니다.")
        except Exception as e:
            self.logger.exception(f"치명적 오류 발생: {e}")
            if self.notifier.enabled:
                self.notifier.notify_error(f"봇이 오류로 종료되었습니다: {str(e)}")
            raise
        finally:
            # 정리 작업
            close_fn = getattr(self.exchange, "close", None)
            if callable(close_fn):
                await close_fn()
            self.logger.info("봇이 종료되었습니다.")


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description="BTC 추세추종 Docker 버전")
    parser.add_argument("--paper-bars", type=int, default=None, help="백테스트용 캔들 개수 (지정 시 백테스트 모드)")
    return parser.parse_args()


async def main():
    """메인 함수"""
    args = parse_args()
    
    # 백테스트 모드
    if args.paper_bars:
        env = load_env()
        config = StrategyConfig(
            symbol=env.get("BTC_TREND_SYMBOL", "BTCUSDT"),
            interval=env.get("BTC_TREND_INTERVAL", "4h"),
            risk_pct=float(env.get("BTC_TREND_RISK_PCT", "1.0")),
            leverage=float(env.get("BTC_TREND_LEVERAGE", "1.0")),
        )
        exchange = PaperExchangeClient(starting_equity=10000.0)
        bot = BTCTrendFollower(config, exchange)
        logger = setup_cloudwatch_logger()
        logger.info(f"백테스트 모드: {args.paper_bars}개 캔들")
        await bot.run_paper_test(bars=args.paper_bars)
        equity = await exchange.fetch_equity()
        logger.info(f"백테스트 완료. 최종 자산: ${equity:,.2f}")
        return
    
    # 실시간 모드
    bot = TradingBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


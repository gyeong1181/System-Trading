# BTC 추세추종 Paper Trading Report

- **Date:** 2025-11-17
- **Data Source:** Binance Futures REST `BTCUSDT` 4h klines (latest 200 bars)
- **Mode:** `python btc_trend_follow.py --paper --interval 4h --paper-bars 200`
- **Initial Equity:** 10,000 USDT
- **Final Equity:** 10,071.95 USDT
- **Net PnL:** +71.95 USDT (+0.72%)
- **Total Trades:** 1 (long)
- **Average Hold:** 1 candle (4시간봉 스윙)
- **Notes:** 4시간봉에서도 ATR 스탑, TP1 50% 청산, 러너+트레일 규칙이 동일하게 작동함을 확인. 더 긴 데이터로 통계 축적 권장.

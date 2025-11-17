# BTC 추세추종 – AuraBot v1.6.1 Python 포팅

대표님의 PineScript 전략을 Python 서비스로 옮겼습니다. EMA20/50, ADX>15, ATR 기반 리스크, Minervini 분할청산, EMA 2봉 플립 강제 종료까지 그대로 구현했고 4시간봉 기본 세팅입니다.

## 구성

- `btc_trend_follow.py` – 메인 실행/CLI (`--paper`, `--real`, `--live`, `--leverage`)
- `exchange.py` – Binance REST/WS, `PaperExchangeClient`, `BinanceLiveExchange`
- `risk.py`, `indicators.py`, `utils.py` – 리스크·지표·로깅
- `reports.py` – 실시간 CSV 리포트 (`reports/trade_log.csv`, `reports/equity_curve.csv`)
- `BTCTrendFollower.service` – `/opt/btc_trend_follow` systemd 유닛
- `logs/btc_trend_follow.log`, `sample_log.txt`, `paper_trading_report.md`
- `BTCTrendFollower_package.zip` – AWS 업로드 ZIP

## 환경

1. 루트 `.env` 또는 `/opt/btc_trend_follow/.env`에 API/텔레그램 키 작성  
   - 실계정 사용 시 `BINANCE_API_KEY`, `BINANCE_API_SECRET`  
   - 옵션: `BTC_TREND_SYMBOL`, `BTC_TREND_INTERVAL`, `BTC_TREND_RISK_PCT`, `BTC_TREND_LEVERAGE`, `BTC_TREND_PAPER_MODE`
2. 의존성:
   ```bash
   pip install pandas numpy httpx websockets python-dotenv
   ```

## 실행

### 페이퍼 / 백테스트
```bash
python btc_trend_follow.py --paper --interval 4h --paper-bars 400
```

### 실시간 (가짜돈)
```bash
tmux new -s btc_trend
python btc_trend_follow.py --live --paper --symbol BTCUSDT --interval 4h --leverage 3
```

### 실시간 (실제돈)
```bash
tmux new -s btc_trend_live
python btc_trend_follow.py --live --real --symbol BTCUSDT --interval 4h --leverage 3
```
> `.env`에 Binance Futures API 키가 있어야 하며, `--real` 또는 `BTC_TREND_PAPER_MODE=false`로 전환합니다.

### AWS systemd
```bash
sudo cp BTCTrendFollower.service /etc/systemd/system/BTCTrendFollower.service
sudo systemctl daemon-reload
sudo systemctl enable --now BTCTrendFollower.service
sudo systemctl status BTCTrendFollower
```

## 리포트/로그

- 실시간 실행 이벤트는 `logs/btc_trend_follow.log`에 기록
- 모든 진입/청산/에쿼티 스냅샷이 `reports/trade_log.csv`, `reports/equity_curve.csv`에 저장되어 엑셀에서 바로 열 수 있음

## 포트폴리오 포인트

- Paper/LIVE 토글(`--paper`/`--real`, `BTC_TREND_PAPER_MODE`)
- systemd + AWS 체크리스트 + GitHub Actions 핸드오버 문서
- 실적 데이터(CSV) 자동 축적 → 클라우드/운용 역량 어필 가능

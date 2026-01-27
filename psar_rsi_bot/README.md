# PSAR + EMA200 + RSI 자동매매 봇 (파라볼릭 전략)

트레이딩뷰 아이디어(PSAR 전환 + EMA200 방향 + RSI 50 필터)를 파이썬으로 구현한 선물 자동매매 봇입니다. AWS EC2에서 24시간 구동하며, GitHub Actions로 자동 배포/재시작합니다.

## 전략 개요
- 롱: PSAR 상승 전환 & 종가 > EMA200 & RSI > 50
- 숏: PSAR 하락 전환 & 종가 < EMA200 & RSI < 50
- 스탑: 스윙 고저점 기준
- 목표: 기본 2R (현재 비활성)
- 청산: PSAR 플립 신호 청산 통일 (TP OFF)

## 실행 준비
1) 의존성 설치
```bash
pip install -r requirements.txt
```
2) .env 작성
- 실거래 키: `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- 모드: `PSAR_RSI_PAPER_MODE=true|false`
- 선택: `PSAR_RSI_SYMBOL`, `PSAR_RSI_SYMBOLS`, `PSAR_RSI_INTERVAL`, `PSAR_RSI_RISK_PCT`, `PSAR_RSI_RR`, `PSAR_RSI_SWING_LOOKBACK`, `PSAR_RSI_LEVERAGE`, `PSAR_RSI_EXIT_ON_FLIP`
- 리스크: `PSAR_RSI_MAX_NOTIONALS`, `PSAR_RSI_RESERVE`, `PSAR_RSI_MARGIN_BUFFER`, `PSAR_RSI_ALERT_COOLDOWN_SEC`

## 실행 예시
- 페이퍼(실시간)
```bash
python psar_rsi_strategy.py --live --paper --symbol BTCUSDT --interval 1h
```
- 멀티 심볼 (예: BTC+SOL)
```bash
python psar_rsi_strategy.py --live --paper --symbols BTCUSDT,SOLUSDT --interval 1h
```
- 실거래
```bash
python psar_rsi_strategy.py --live --real --symbol BTCUSDT --interval 1h
```

## Docker 실행 (선택)
> systemd와 Docker를 동시에 사용하면 중복 실행될 수 있습니다. 한 가지만 사용하세요.

```bash
docker compose up -d --build
docker compose logs -f
```

## 운영/배포
- GitHub Actions → EC2 `/opt/psar_rsi_bot`로 rsync
- systemd로 상시 실행
```bash
sudo systemctl daemon-reload
sudo systemctl restart psar_rsi_bot
sudo systemctl status psar_rsi_bot --no-pager
```

## 로그/리포트
- 로그: `logs/psar_rsi_bot.log`
- 거래 로그: `reports/trade_log.csv`
- 에쿼티: `reports/equity_curve.csv`

## 아키텍처/운영 증빙
![Architecture](docs/Architecture/Architecture.png)
![Mermaid Architecture](docs/Architecture/Mermaid_Architecture.png)
![CloudWatch Logs Insights](docs/cloudwatch_insights2.png)
![GitHub Actions](docs/Github_Actions_CICD_capture.png)
![Telegram Alert](docs/telegram_alert.png)

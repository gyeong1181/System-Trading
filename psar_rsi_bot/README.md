# PSAR + EMA200 + RSI 자동매매 봇 (파라볼릭 전략)

트레이딩뷰 아이디어(PSAR 전환 + EMA200 방향 + RSI 50 필터)를 파이썬으로 구현한 선물 자동매매 봇입니다. AWS EC2에 올려 24시간 돌리고 있으며, GitHub Actions로 코드 변경 시 자동 배포/재시작합니다. 클라우드 엔지니어 취업 대비용이자 실제 운영 파이프라인 구축 목적입니다.

## 전략 개요
- 진입:  
  - 롱: PSAR 상승 전환 & 종가 > EMA200 & RSI > 50  
  - 숏: PSAR 하락 전환 & 종가 < EMA200 & RSI < 50
- 리스크/청산: 스윙 고저점 스탑, 기본 2R 목표가, PSAR 플립 시 조기 청산 옵션.
- 리스크 사이징: `리스크자본 = 계좌 * (risk_pct/100) * leverage`, `수량 = 리스크자본 / 스탑거리`.

## 파일 구조 (핵심)
- `psar_rsi_strategy.py` : 메인 실행기(REST 워밍업 + WS 실시간/백테스트)
- `indicators.py` : EMA/RSI/PSAR 계산 및 플립 신호
- `exchange.py` : Binance REST/WS 래퍼, 페이퍼/LIVE 공용
- `reports.py` : 트레이드/에쿼티 CSV 로그
- `.github/workflows/deploy.yml` : main 푸시 시 EC2 `/opt/psar_rsi_bot`로 rsync 후 systemd 재시작
- `env_template.txt` : .env 템플릿

## 실행 준비
1) 의존성 설치
```bash
pip install -r requirements.txt
```
2) .env 작성 (예: 루트 또는 `/opt/psar_rsi_bot/.env`)
- 실거래 키: `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- 모드: `PSAR_RSI_PAPER_MODE=true|false`
- 선택: `PSAR_RSI_SYMBOL`, `PSAR_RSI_INTERVAL`, `PSAR_RSI_RISK_PCT`, `PSAR_RSI_RR`, `PSAR_RSI_SWING_LOOKBACK`, `PSAR_RSI_LEVERAGE`, `PSAR_RSI_EXIT_ON_FLIP`

## 실행 예시
- 페이퍼 백테스트(REST):  
  ```bash
  python psar_rsi_strategy.py --paper --paper-bars 750
  ```
- 실시간 페이퍼(WS):  
  ```bash
  python psar_rsi_strategy.py --live --paper --symbol BTCUSDT --interval 1h
  ```
- 실거래(WS):  
  ```bash
  python psar_rsi_strategy.py --live --real --symbol BTCUSDT --interval 1h
  ```
  (.env에 실키 + `PSAR_RSI_PAPER_MODE=false` 필수)

## AWS 배포/운영
- GitHub Actions: main 푸시 → `/opt/psar_rsi_bot`로 rsync → `systemctl daemon-reload && systemctl restart psar_rsi_bot`
- 수동 재시작:
  ```bash
  cd /opt/psar_rsi_bot
  sudo systemctl daemon-reload
  sudo systemctl restart psar_rsi_bot
  sudo systemctl status psar_rsi_bot --no-pager
  ```
- 로그:
  ```bash
  sudo journalctl -u psar_rsi_bot -f
  ```

## 운영 메모
- 현재 기본 값: BTCUSDT, 1h. 다른 티커/주기는 `--symbol`, `--interval`로 변경.
- venv는 현재 사용하지 않음(필요 시 ExecStart에 venv 파이썬 지정).
- API 키가 없으면 실거래는 실패(바로 종료), 페이퍼는 동작하되 알림은 비활성화.

## 앞으로 확장
- 모니터링/시각화: Grafana/Prometheus 예정
- 오케스트레이션: Kubernetes(미도입)
- 알림 확장: Telegram/Slack/Email
- 백테스트 고도화: 슬리피지/수수료 시뮬, 메트릭 리포트

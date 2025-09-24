# Swing Alert MVP

BTC·ETH 단기 스윙 포지션 보조 시스템을 위한 MVP 코드베이스입니다. 데이터 수집 → 기술적 시그널 → 리스크 관리 → 텔레그램 알림까지 한 번에 실행할 수 있는 구조를 제공합니다.

## 프로젝트 구조
```
project/
├── alerts/            # 텔레그램 알림 모듈
├── backtest/          # 간단 백테스트 엔진
├── data/              # 거래소 데이터 수집 모듈 (Binance)
├── notebooks/         # 실험/점검용 주피터 노트북
├── risk/              # 리스크 관리 로직
├── signals/           # EMA, RSI 다이버전스, 피보, 프랙탈 모듈
├── main.py            # 전체 파이프라인 실행 스크립트
└── requirements.txt   # 필수 파이썬 패키지
```

## 빠른 시작
1. **의존성 설치**
   ```bash
   cd project
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **환경변수 설정** (`project/.env` 생성)
   ```env
   BINANCE_API_KEY=...
   BINANCE_API_SECRET=...
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ACCOUNT_BALANCE=10000
   ```
   - 키가 없다면 `BINANCE_*` 항목은 비워두면 되고, 텔레그램 토큰/챗아이디를 입력하지 않으면 로그로만 알림이 출력됩니다.

3. **실행**
   ```bash
   python main.py  # RUN_ONCE=true 기본값 → 15분봉 평가 1회 수행
   ```
   - 지속 모니터링을 원하면 `RUN_ONCE=false` 및 `EVALUATION_INTERVAL_SECONDS=900` 등을 `.env` 또는 셸에서 지정하세요.

4. **노트북 점검**
   ```bash
   jupyter notebook notebooks/step1_data_chart.ipynb
   ```
   - 데이터 다운로드가 막히면 자동으로 더미 데이터를 생성해 차트를 확인할 수 있습니다.

## 모듈 개요
- `data/binance_client.py` — 환경변수 기반 인증을 사용하는 ccxt 래퍼. BTCUSDT/ETHUSDT 15분봉 최근 500개를 DataFrame으로 반환합니다.
- `signals/` — EMA 필터, RSI 다이버전스, 피보나치 레벨, 프랙탈 스윙을 점수화합니다.
- `risk/risk_manager.py` — 계좌 1% 손실, 최소 R:R 1:1.8, 일일 -2% 컷 규칙을 기반으로 포지션 크기를 계산합니다.
- `alerts/telegram_bot.py` — 조건 충족 시 텔레그램 메시지를 전송하거나(환경 미설정 시 로그로 대체) 포맷팅합니다.
- `backtest/backtest_engine.py` — 시그널 열이 포함된 DataFrame을 받아 수익률/샤프/드로우다운을 리포트합니다.
- `main.py` — 15분마다(기본 1회) 데이터 수집 → 시그널 → 리스크 → 알림 순으로 실행합니다.

## 주의 사항
- Binance/텔레그램 API 호출은 네트워크 정책에 따라 차단될 수 있습니다. 이 경우 코드에서 예외를 처리하여 안내 메시지를 출력합니다.
- 본 프로젝트는 연구 및 교육 목적이며, 실제 거래 손실에 대한 책임은 사용자에게 있습니다.

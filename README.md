# 시스템 트레이딩 봇

이 저장소는 [ccxt](https://github.com/ccxt/ccxt) 라이브러리를 기반으로 한 이더리움 선물 자동매매 봇입니다. 전략은 EMA 트렌드 필터와 RSI, ADX, ATR 기반의 리스크 관리를 조합합니다.

## 기능
- 빠른/느린 EMA 교차와 RSI, ADX 필터를 사용해 진입 신호 생성
- 고정 손절선, ATR 기반 추적 손절, 일일 손실 제한 등 리스크 관리 기능
- 러너 포지션 관리를 위한 부분 청산 및 피라미딩 로직
- 체결 및 런타임 오류에 대한 텔레그램 알림
- 백테스트 스크립트와 Optuna 기반 파라미터 튜너 포함
- 컨테이너 배포를 위한 Dockerfile과 요구사항 파일 제공

## 시작하기
1. 봇 폴더로 이동:
   ```bash
   cd systemTrading/EMA_RSI/25.08.10\ EMA_RSI_ADX_ATR
   ```
2. 의존성 설치:
   ```bash
   pip install -r requirements.txt
   ```
   또는 Docker 이미지 빌드:
   ```bash
   docker build -t eth-bot .
   ```
3. API 및 텔레그램 자격 증명(`API_KEY`, `SECRET_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`)이 담긴 `.env` 파일 생성
4. 봇 실행:
   ```bash
   python ema_rsi_adx_atr_eth_bot.py
   ```

## 백테스트 및 튜닝
`튜닝기/backtest/` 폴더의 스크립트를 이용해 오프라인 백테스트와 Optuna 기반 파라미터 튜닝을 수행할 수 있습니다. 다양한 파라미터 조합을 직접 시험해 보세요.

## 면책 조항
이 코드는 교육 목적이며 사용에 따른 책임은 사용자에게 있습니다.

# PSAR + EMA200 + RSI(50) 자동매매 봇 (Binance Futures)

트레이딩뷰 오픈 소스 아이디어(파라볼릭 SAR + EMA200 + RSI 50 기준선)를 파이썬으로 재구현했습니다.  
종가 기준 조건을 만족하면 포지션을 열고, 최근 스윙 고/저점을 손절로, 기본 2R 목표가를 사용합니다.

## 전략 규칙
- 롱 진입: PSAR가 상승 전환 AND 종가 > EMA200 AND RSI > 50
- 숏 진입: PSAR가 하락 전환 AND 종가 < EMA200 AND RSI < 50
- 손절: 최근 스윙 고점/저점(lookback 기본 5봉)
- 목표가: 2R (리스크 대비 2배)
- 옵션: PSAR 반전 시 조기 청산 가능

## 실행 준비
1) 의존성 설치
```bash
pip install -r requirements.txt
```
2) 환경변수 파일(.env) 작성  
`env_template.txt`를 복사하여 `.env`를 만들고 값 채우기.
필수(실거래 시): `BINANCE_API_KEY`, `BINANCE_API_SECRET`  
선택: `PSAR_RSI_SYMBOL`, `PSAR_RSI_INTERVAL`, `PSAR_RSI_RISK_PCT`, `PSAR_RSI_RR`, `PSAR_RSI_SWING_LOOKBACK`, `PSAR_RSI_LEVERAGE`, `PSAR_RSI_PAPER_MODE`, `PSAR_RSI_EXIT_ON_FLIP`

## 실행 예시
- REST 기반 페이퍼 백테스트:
```bash
python psar_rsi_strategy.py --paper --paper-bars 750
```
- 실시간 스트림(페이퍼 모드):
```bash
python psar_rsi_strategy.py --live --paper --symbol BTCUSDT --interval 1h
```
- 실거래 모드(위험 주의):
```bash
python psar_rsi_strategy.py --live --real --symbol BTCUSDT --interval 1h
```

## 주요 파일
- `psar_rsi_strategy.py`: 전략 실행기 (REST 워밍업 + WS 실시간)
- `indicators.py`: EMA/RSI/PSAR 계산, 플립 신호 생성
- `exchange.py`: Binance REST/WS 래퍼, 페이퍼/LIVE 공용 인터페이스
- `utils.py`: 캔들 구조, 로거, 환경 로더
- `reports.py`: 트레이드/에쿼티 CSV 로그
- `env_template.txt`: 환경변수 템플릿
- `requirements.txt`: 필요 패키지 목록

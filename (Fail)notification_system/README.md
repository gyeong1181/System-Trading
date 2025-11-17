# 시스템 트레이딩 모음집

이 저장소는 두 가지 자동매매 전략을 제공합니다.

- `pair_trading/` – BTC와 ETH를 이용한 평균회귀형 페어 트레이딩 봇
- `systemTrading/` – EMA, RSI, ATR, ADX를 결합한 이더리움 추세추종 봇

각 전략 폴더에는 필요한 실행 파일, 설정 예제, 요구 패키지 및 개별 README가 포함되어 있습니다.

## 빠른 시작

```bash
python -m venv venv && source venv/bin/activate
pip install -r <전략 폴더>/requirements.txt
cp <전략 폴더>/.env.example .env  # API 키와 텔레그램 정보를 입력
python <전략 폴더>/main.py --mode backtest
```

실거래 드라이런을 시작하려면 다음과 같이 실행합니다.

```bash
python <전략 폴더>/main.py --mode live
```

실제 주문을 원한다면 각 전략의 `config.yaml`에서 `dry_run` 값을 `false`로 변경하세요.

## 참고
- 각 전략의 README에서 세부 사용법과 위험 고지를 확인하세요.
- Dockerfile을 통해 컨테이너 배포도 가능하지만 기본적으로는 로컬 실행을 권장합니다.

## 면책 조항
이 코드는 교육 및 연구 목적을 위해 제공되며, 모든 거래 책임은 사용자에게 있습니다.

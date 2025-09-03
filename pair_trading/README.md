# BTC–ETH 페어 트레이딩 봇

이 패키지는 Binance USDT-M 선물에서 BTC와 ETH를 이용한 평균회귀 전략을 구현합니다. 봇은 빠른 백테스트와 실거래(dry-run 기본)를 수행할 수 있습니다.

## 파일

- `main.py` – 백테스트 및 실거래 진입점
- `config.yaml` – 전략 파라미터
- `requirements.txt` – Python 의존성
- `.env.example` – 환경 변수 템플릿
- `Dockerfile` – 컨테이너 스펙(선택 사항)

## 설치 및 실행

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # API 키와 텔레그램 정보를 입력
python main.py --mode backtest
```

라이브 트레이딩을 시작하려면(기본은 dry-run):

```bash
python main.py --mode live
```

실제 주문을 위해서는 `config.yaml`에서 `dry_run` 값을 `false`로 변경하세요. 코드를 검토하고 사용은 본인의 책임 하에 진행하시기 바랍니다.

## AWS/Docker

간단한 Dockerfile이 포함되어 있습니다. 아래 명령으로 빌드 및 실행할 수 있습니다:

```bash
docker build -t pairtrading .
docker run -d pairtrading
```

## 면책 조항

이 코드는 교육용으로 제공되며, 거래에는 항상 위험이 따릅니다.

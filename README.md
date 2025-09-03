# 시스템 트레이딩 전략 모음

이 저장소는 여러 알고리즘 트레이딩 프로젝트를 모아 관리합니다.

- `pair_trading/` – BTC–ETH 평균회귀 전략으로 백테스트와 실거래(드라이런) 모드를 제공합니다. 자세한 설명은 `pair_trading/README.md`를 참고하세요.
- `trend_following/` – EMA + RSI + ATR + ADX 조합의 추세추종 전략입니다. 사용 방법은 `trend_following/README.md`에 정리되어 있습니다.

각 폴더에는 고유한 설정 파일, 의존성 목록, 그리고 선택적인 Dockerfile이 포함되어 있습니다. 가상환경을 생성하고 해당 폴더의 `requirements.txt`를 설치한 뒤 `.env.example`을 `.env`로 복사하여 API 키를 입력하고 `main.py`를 실행하면 됩니다.

## 면책 조항

이 코드는 교육 목적으로 제공됩니다. 실제 거래에는 큰 위험이 수반되므로, 모든 결정과 책임은 사용자에게 있습니다.


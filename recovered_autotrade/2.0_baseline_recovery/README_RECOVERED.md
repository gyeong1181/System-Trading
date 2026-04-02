# Recovered Autotrade Bundle

이 폴더는 `exitant/autotrade-app-okx-2.0-gold` 이미지에서 확인된 전략 로직을
`실제 도커 내용물에 최대한 가깝게` 보관하려는 목적의 최소 복원본입니다.

## 왜 `pyc`가 바로 안 열리나

- `autotrade2.pyc`는 Python 원본 `.py`가 아니라 컴파일된 바이트코드입니다.
- 따라서 메모장이나 일반 에디터로 열면 사람이 읽기 좋은 코드가 아니라 바이너리/깨진 문자처럼 보입니다.
- 읽으려면 디컴파일 또는 디스어셈블이 필요합니다.

## 이 폴더에 남긴 파일

- `autotrade2.pyc`
  - 실제 전략 엔트리포인트에 가장 가까운 핵심 바이트코드 증거물
- `autotrade2_reconstructed.py`
  - 위 `pyc`와 분석 결과를 바탕으로 사람이 읽을 수 있게 재구성한 근사 소스
- `STRATEGY_SYSTEM_ANALYSIS.md`
  - 전략 구조, 실행 흐름, 외부 연동, 운영 시스템 설명
- `STRATEGY_PSEUDOCODE.md`
  - 함수별 의사코드

## 정확도

- `autotrade2.pyc`: 원본 실행 로직의 직접 증거
- `autotrade2_reconstructed.py`: 원본과 1:1 동일하지 않음
- 다만 전략 흐름, 주요 함수 역할, 종목, 주문 방식, 순환매 상태 관리는 최대한 반영

## 현재 기준으로 확인된 핵심 사실

- 종목: `XAU-USDT-SWAP`
- 데이터 소스: OKX 5분봉 50개
- 주요 판단 요소: RSI, Bollinger Band, Fibonacci, swap threshold
- 결과: `open long rotate`, `open short rotate`, `stay`
- 주문 방식: `cross` 모드 지정가 + TP 부착
- 제어/UI: Telegram
- 운영 루프: 약 10초 주기

## 한계

- 원본 `.py` 두 개를 그대로 확보한 것은 아님
- 주석, 원래 변수명 일부, 테스트 전략 파일은 미복원
- `autotrade2_reconstructed.py`는 복원본이며 원문 복사본이 아님

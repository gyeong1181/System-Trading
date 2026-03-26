# Bybit 개인 트레이딩 연구 레포

현재 레포는 범위를 의도적으로 줄인 상태입니다. 목표는 전략을 늘리는 것이 아니라, `S1`을 살릴 수 있는지 빠르게 검증하고 `S2`를 보조 후보로만 확인하는 것입니다.

## 현재 기본 경로

- 주력 전략: `S1` 돈치안 돌파
- 보조 전략: `S2` EMA + RSI 눌림목
- 제외 전략: `S3` 볼린저 평균회귀
- 기본 심볼: `ETHUSDT`
- 기본 연구 시간프레임: `4시간`, `일봉`
- 보조 심볼 `BTCUSDT`는 기본 비활성 상태입니다.

## 이번 경로에서 바뀐 점

### S1

- EMA200 레짐 필터 추가
- ADX 필터 추가
- 쿨다운 / 중복 진입 방지 추가
- ATR 스탑 유지
- 피라미딩 없음

### S2

- 복잡한 크로스 중심 구조 제거
- EMA200 방향만 보고 눌림목 / 반등만 진입
- RSI 회복 / 약화 기준으로 단순화
- ATR 스탑 + time stop 반영

### S3

- 코드 파일은 남겨두되 기본 실행에서 제외
- `configs/settings.toml` 에서 `enabled = false`

## 연구 기준

- Bybit taker fee 반영
- 슬리피지 반영
- funding 반영
- 시그널은 종가 기준
- 체결은 다음 바 시가 기준
- 워크포워드: `365일 in-sample / 90일 out-of-sample / 30일 step`
- 최소 히스토리: `3년`

## 최종 판정 기준

- `PF > 1.10`
- `MDD < 10%`
- `양전 월 비율 >= 50%`
- `누적 수익 > 0`
- 지나치게 적은 거래 수는 경고
- 플래토 / 강건성 점검 통과 여부 확인

최종 라벨:

- `candidate`
- `shadow`
- `reject`

## 설치

```powershell
cd "d:\코딩\자동매매\AI 자동매매 제작 프로젝트\bybit_personal_trading_system"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 최소 실행 순서

```powershell
copy .env.example .env
python -m src.cli bootstrap
python -m src.cli data-fetch
python -m src.cli research-all
python -m src.cli report
```

`Bybit API / Telegram` 값이 아직 없어도 `bootstrap`, `data-fetch`, `research-all`, `report` 는 먼저 가능합니다.

## Make 기준 최소 명령

```powershell
make bootstrap
make data-fetch
make research-all
make report
```

## 결과 파일

- `reports/research_report.html`
- `reports/research_report.csv`
- `reports/research_report.json`

## 현재 운영 해석

- `S1`은 여전히 연구 대상이지만 PF와 MDD를 함께 만족시키지 못하면 바로 후보로 올리지 않습니다.
- `S2`는 보조 전략이므로 데모 검증 우선입니다.
- `S3`는 이번 경로에서 판단 대상이 아닙니다.

## 실행 제어

```powershell
make status
make pause
make resume
make kill
```

Telegram 명령:

- `/status`
- `/pause`
- `/resume`
- `/kill`

## 주의

- 지금 단계에서는 전략 추가, 자산군 확대, UI 추가를 하지 않습니다.
- 먼저 `ETHUSDT 4시간 vs 일봉` 비교 결과를 기준으로 후보 여부를 정합니다.
- 후보가 나오지 않으면 파이프라인을 더 넓히지 말고 S1/S2만 한 번 더 조정합니다.

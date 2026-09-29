# Incident Recovery Record

이 문서는 실제 발생한 장애와 후속 조치를 구분해 기록합니다. 자동 재시작 정책이 있다고 해서 모든 장애가 자동 복구되거나 수동 개입이 없었다는 의미는 아닙니다.

## Incident 1 | 2025-12-22 systemd 최초 기동 실패

### 증상

서비스가 의도한 실시간 실행 상태를 유지하지 못했습니다.

### 확인한 원인

1. unit file 경로가 `/etc/systemd/system`이 아니라 `/etc/systmed`로 잘못 작성됨
2. `ExecStart`가 존재하지 않는 `bot_main.py`를 참조함
3. 실행 옵션이 누락되어 `run_live()`가 아니라 `run_paper_test()` 실행 후 종료됨

현재 코드에서도 `--live`가 있을 때 `run_live()`를 호출하고, 없으면 `run_paper_test(bars=args.paper_bars)`를 호출하는 분기를 확인할 수 있습니다.

### 조치

- unit file을 `/etc/systemd/system`으로 수정
- `ExecStart`를 실제 파일인 `psar_rsi_strategy.py`로 수정
- `--live --paper --paper-bars 750` 추가
- `systemctl daemon-reload` 후 서비스 restart
- `systemctl status`에서 `Active: active (running)` 확인

### 재시작 정책

```ini
[Service]
Restart=on-failure
RestartSec=10
```

`RestartSec=10`의 설계 기준은 FastAPI 기동 약 5초와 여유 5초입니다. 저장소에서 사용하는 재시작 대기값은 10초입니다.

## Incident 2 | 2026-01-26 Binance 400/minNotional

### 타임라인

- 18:27:51: Binance 400/minNotional 오류 확인
- 18:31:03: 정상 주문 재개 확인
- 단일 사례 대응 시간: 3분 12초

이 수치는 한 건의 장애 타임라인이며 평균 장애 해결시간, MTTR 또는 `RestartSec`가 아닙니다.

### 후속 조치

- 거래소 심볼 필터의 `minNotional`, `stepSize`, `tickSize` 확인
- 주문 전 수량·가격 정규화 및 검증 로직 적용
- 오류와 주문 스킵 사유를 로그·메트릭·Telegram으로 확인할 수 있도록 구성
- 관측 기간 동안 동일 문제가 다시 확인되지 않았으나, 모든 기간에 대한 절대 수치로 일반화하지 않음

## Incident 3 | Binance API 401 / IP whitelist 불일치

### 증상과 원인

실제 401 인증 장애가 발생했습니다. Public IP 변경으로 Binance API key의 IP whitelist와 서버 IP가 일치하지 않는 문제를 확인했습니다.

### 조치

- 변경된 Public IP와 whitelist를 확인해 수정
- IP 변경 위험을 줄이기 위해 Elastic IP 적용
- 시작 시 API 연결 상태를 확인하는 사전 검증 로직 추가
- 인증 오류 지표와 Telegram 알림 구성

이는 “처음부터 예방되어 장애가 없었다”는 사례가 아닙니다. 장애 확인과 수동 조치 후 재발 방지책을 추가한 사례입니다.

## Incident 4 | Oregon 이전 실험

### 목적과 실행 범위

비용과 운영 구조 개선을 위해 Oregon(`us-west-2`) 이전을 실험했습니다. Terraform `apply`를 실제 수행해 EC2, IAM, Security Group, Elastic IP를 만들고 Docker Compose 기반 멀티 컨테이너 기동을 시도했습니다.

### 단계별 진단

- cloud-init 실패
- Amazon Linux 2023 패키지 충돌
- 서비스 기동 문제
- GHCR private image 인증 오류
- 작업 PC Public IP 변경으로 SSH Security Group 허용 CIDR 불일치
- Binance Futures API의 Oregon 리전 HTTP 451 응답

HTTP 451은 코드나 네트워크 설정으로 해결 가능한 문제가 아닌 외부 서비스의 지역 제약이었습니다. 따라서 완전한 Oregon 마이그레이션 또는 멀티리전 프로덕션 운영으로 정리하지 않습니다.

최종 역할:

- 서울: PSAR 운영/포트폴리오 환경(systemd)
- Oregon: 외부 OKX 전략의 Terraform/Docker Compose 실험 환경

## Recovery and Monitoring Boundaries

| 계층 | 구성 | 사실 범위 |
|---|---|---|
| Process | systemd | 프로세스 실패 시 `RestartSec=10` 정책으로 재시작 시도 |
| Metrics | Prometheus | Webhook, 주문 결과, API 오류, Telegram 전송 지표 수집 |
| Dashboard / Alert | Grafana | 메트릭 시각화와 Alert Rule 구성 |
| Notification | Telegram | 이상·오류·체결 알림 및 운영자 에스컬레이션 |
| Manual response | SSH / runbook | whitelist, 설정, 인프라·외부 제약은 수동 확인과 조치가 필요할 수 있음 |

Grafana 알림이 직접 `systemctl restart`를 실행한다고 단정할 구성 근거는 저장소에서 확인되지 않았습니다. 자동 재시작은 systemd의 역할이고, Prometheus/Grafana/Telegram은 감지·시각화·통지 계층으로 설명합니다.

## Evidence

- [모니터링 구성 가이드](../deploy/monitoring/README.md)
- [운영 체크리스트](operations_checklist.md)
- [Oregon 실험 일지](daily_report_2026-03-16.md)
- [리전 역할 분리 결정 로그](decision_log/2026-03-17_region_role_split.md)
- [Prometheus Targets](monitoring/prometheus_targets_up.jpg)
- [Grafana Alert Rules](monitoring/grafana_alert_rules.jpg)

## Interview Summary

“장애가 없었다”가 아니라, 실제 장애에서 로그와 설정을 확인해 원인을 분리하고, systemd 재시작 정책·모니터링·알림·runbook과 재발 방지 로직을 단계적으로 보완했다고 설명합니다.

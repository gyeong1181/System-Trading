# 데일리 리포트 2026-03-16

## 오늘 작업 요약

오늘 작업의 핵심은 단순히 자동매매 봇을 하나 더 돌리는 것이 아니라, 실제 운영 비용을 줄이기 위해 분산된 컨테이너 운영 구조를 AWS 단일 인스턴스 멀티 컨테이너 구조로 재편하는 것이었다.

기존에는 Render에서 전략 컨테이너를 각각 따로 운영했고, 총 3개를 돌리면서 월 서버 비용이 약 21,000원 수준까지 발생했다. 컨테이너 1개당 약 7,000원 수준의 고정비가 들어가는 구조였다. 이 비용 구조를 줄이기 위해 외부 전략 2개를 AWS Oregon EC2 한 대에 Docker Compose로 함께 운영하는 방향으로 전환을 시도했다.

동시에, 기존에 서울 리전에서 systemd 기반으로 운영 중인 PSAR webhook executor는 그대로 유지한 채, Oregon 쪽에서 Terraform 기반 IaC와 멀티 컨테이너 운영 구조를 실제로 검증했다.

---

## 현재 운영 구조

- 서울 리전:
  - 기존 PSAR webhook executor 실거래 운영 지속
  - systemd 기반 단일 서비스 구조
- Oregon 리전:
  - Terraform으로 생성한 EC2
  - `/opt/trading-stack` 기반 Docker Compose 구조
  - 대상 컨테이너:
    - `psar_rsi` 커스텀 컨테이너
    - `OKX Nasdaq` 외부 vendor 컨테이너
    - `OKX Gold` 외부 vendor 컨테이너
- 비밀값 관리:
  - AWS SSM Parameter Store 사용

---

## 주요 진행 사항

### 1. Terraform 기반 Oregon 환경 실전 적용

- `terraform plan` 수준이 아니라 실제 `terraform apply`까지 수행해 Oregon 리전에 신규 EC2, IAM, Security Group, Elastic IP 생성 흐름을 검증했다.
- 단순히 인프라를 만든 것이 아니라, user_data를 통해 Docker 설치, 디렉터리 생성, SSM sync, compose stack 배치까지 이어지는 운영 흐름을 점검했다.

### 2. Docker 멀티 컨테이너 운영 구조 검증

- 외부 vendor 전략 2종을 AWS 단일 인스턴스에 함께 올리는 흐름을 실제로 검증했다.
- `OKX Nasdaq` 이미지는 정상 pull 확인.
- `OKX Gold` 이미지는 초기에 image reference가 잘못되어 실패했지만, `exitant/autotrade-app-okx-2.0-gold:latest`로 수정 후 정상 pull 확인.
- 이 과정에서 "컨테이너가 안 뜬다"는 현상을 단순 장애로 보지 않고, 이미지명 문제와 레지스트리 인증 문제를 분리해서 추적했다.

### 3. GHCR private image pull 병목 분리

- 커스텀 PSAR 컨테이너는 `ghcr.io/gyeong1181/quant-fleet-core:latest` 경로를 사용하도록 정리했다.
- 그러나 Oregon EC2에서 GHCR private image pull이 `unauthorized`로 실패하는 것을 확인했다.
- 이 문제는 Docker 엔진 문제나 네트워크 문제가 아니라, GHCR 인증 또는 package visibility 문제로 원인을 분리했다.
- 즉, 현재 남은 핵심 병목은 PSAR 이미지 인증 처리 하나로 좁혀졌다.

### 4. 비용 절감 관점 정리

- 기존 Render 분산 운영 구조:
  - 전략 컨테이너 3개
  - 월 서버 비용 약 21,000원 수준
- 전환 목표:
  - AWS 단일 인스턴스에 전략 여러 개를 묶어 운영
  - 고정비 절감
  - 운영 구조 단순화
  - 이후 Terraform 기반 재현성과 이식성까지 확보

이 비용 절감 시도는 단순한 "싼 서버 찾기"가 아니라, 운영 구조를 다시 설계해서 비용과 관리 복잡도를 동시에 낮추려는 시도라는 점에서 의미가 있다.

---

## 트러블슈팅 정리

### 이슈 1. cloud-init 실패

현상:
- Oregon EC2에서 `sudo cloud-init status --wait` 실행 시 `error` 발생

분석:
- 초기에는 Amazon Linux 2023 패키지 충돌 문제(`curl` 계열)로 부트스트랩이 중단됐다.
- 이후 패키지 처리 로직을 보완한 뒤에는 `trading-strategy-stack.service` 기동 실패가 cloud-init 실패로 이어진다는 점을 확인했다.
- 즉, Terraform 자체가 깨진 것이 아니라, 인스턴스 부팅 후 런타임 단계에서 Docker stack이 실패한 것이었다.

조치:
- `user_data.sh.tftpl`의 패키지 설치 경로를 보완했다.
- Docker Compose plugin 설치 실패 시 fallback 경로를 추가했다.
- stack 기동 실패가 전체 bootstrap을 치명적으로 종료시키지 않도록 로직을 보완했다.

결과:
- 인프라 생성과 기본 bootstrap 흐름은 재현 가능 수준으로 정리됐다.
- 남은 병목은 런타임 이미지 인증 문제로 좁혀졌다.

### 이슈 2. GHCR private image unauthorized

현상:
- `sudo docker pull ghcr.io/gyeong1181/quant-fleet-core:latest` 시 unauthorized 발생

분석:
- vendor 이미지 2개는 pull 가능했고, PSAR 이미지 만 실패했다.
- 따라서 Docker 네트워크나 인스턴스 outbound 문제는 아니었다.
- 원인은 GHCR private package 인증 또는 공개 범위 설정 문제로 정리됐다.

조치:
- GHCR username/token을 SSM으로 주입하는 방향을 Terraform 코드에 반영했다.
- 즉시 운영 복구 관점에서는 EC2에서 `docker login ghcr.io` 후 개별 `docker pull`로 문제를 분리 확인하는 방식을 택했다.

결과:
- 현재 남은 핵심 작업은 GHCR 인증 마무리와 PSAR 컨테이너 기동 검증이다.

### 이슈 3. SSH 접속 불가

현상:
- 노트북 재부팅 후 Oregon EC2에 SSH timeout 발생

분석:
- 작업자의 공인 IP가 바뀌었지만, Terraform-managed security group은 예전 IP를 허용한 상태였다.

조치:
- `terraform.tfvars`의 `ssh_allowed_cidrs`, `monitoring_allowed_cidrs`를 현재 IP 기준으로 수정하고 apply하는 패턴을 정리했다.

결과:
- 인프라 문제처럼 보였던 접속 이슈를 네트워크 허용 IP 문제로 분리해 정리했다.

---

## 문서화 및 포트폴리오 반영

오늘 기준으로 다음 문서를 운영 상태에 맞게 정리했다.

- 루트 포트폴리오 README
- PSAR 프로젝트 README
- 운영 체크리스트
- 오늘자 데일리 리포트

특히 README에는 다음 내용을 반영했다.

- Oregon Terraform 이전 진행 상황
- 3-container stack 운영 구조
- Render 분산 운영 비용을 AWS 단일 인스턴스로 줄이려는 시도
- vendor 이미지 인증/참조 문제를 운영 관점에서 분리 추적한 경험

---

## 현재 남은 작업

1. GHCR 인증 마무리 후 `psar_rsi` 컨테이너 pull 성공 확인
2. Oregon에서 3개 컨테이너 동시 기동 확인
3. PSAR 실체결 여부 또는 최소한 로그/텔레그램 기준 정상 흐름 확인
4. Prometheus / Grafana를 Oregon 쪽에 다시 연결
5. Oregon 안정화 후 서울 리전 기존 PSAR 서버 중지

---

## 다음 출근 시 바로 할 일

1. Oregon EC2 접속
2. GHCR PAT 또는 package visibility 문제를 마무리해서 `psar_rsi` 이미지 pull 성공시키기
3. `/opt/trading-stack`에서 3개 컨테이너 `up -d` 후 `ps`, `logs` 확인
4. PSAR 체결 또는 최소한 webhook/log/telegram 흐름 확인
5. Prometheus / Grafana 재기동 및 target/health 확인
6. 이상 없으면 서울 리전 `psar_rsi_bot` 중지 후 관찰 단계로 전환

---

## 한 줄 결론

오늘 작업은 단순한 서버 이전이 아니라, 분산 전략 운영 구조를 비용 절감형 AWS 멀티 컨테이너 구조로 재편하고, 그 과정을 Terraform과 운영 문서로 재현 가능하게 만드는 단계였다.

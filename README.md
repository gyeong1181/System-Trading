# 김경훈 | Cloud / Infrastructure Engineer

실제로 운영 가능한 자동화 시스템을 직접 구축하고, AWS EC2 운영과 Linux/systemd 장애 대응, 배포 자동화, 모니터링, IaC, 컨테이너 및 Kubernetes 로컬 배포 검증까지 경험한 신입 지원자의 포트폴리오입니다.

자동매매는 운영 문제를 다룬 도메인입니다. 이 저장소의 핵심은 수익률이 아니라 **서비스를 배포하고 관측하며 장애 원인을 분리 진단한 Cloud / Infrastructure / DevOps 경험**입니다.

## 지원 분야

- Cloud Engineer
- Infrastructure Engineer
- DevOps Engineer

## 핵심 역량

- AWS EC2 서울 리전에서 FastAPI 기반 Webhook Executor 운영
- Linux/systemd 서비스 구성 및 2025-12-22 초기 기동 장애 대응
- GitHub Actions와 SSH/rsync를 이용한 배포 자동화
- Prometheus, Grafana, CloudWatch, Telegram 기반 메트릭·로그·알림 구성
- Terraform `apply`로 Oregon 리전의 EC2, IAM, Security Group, Elastic IP 생성
- cloud-init, Amazon Linux 2023 패키지 충돌, GHCR 인증, SSH 허용 CIDR 문제 분리 진단
- Docker Compose 기반 멀티 컨테이너 운영 실험
- Kubernetes(Minikube) 배포 검증과 Kustomize dev/prod 환경 분리
- Terraform 기반 VPC/EKS/ECR 구성 작성 및 `terraform plan` 검증

## Project 01 | AWS EC2 기반 운영형 자동화 시스템

서울 리전에서 FastAPI Webhook Executor를 Linux/systemd로 운영한 프로젝트입니다. GitHub Actions + SSH/rsync 배포, Prometheus/Grafana/CloudWatch 관측, Telegram 알림, 실제 장애 대응을 다룹니다.

- Seoul: EC2, Linux, systemd, FastAPI, CI/CD, monitoring
- Oregon 실험: Terraform `apply`, Docker Compose 멀티 컨테이너, cloud-init/GHCR/SSH Security Group 문제 진단
- 최종 판단: Binance Futures HTTP 451 지역 제약을 확인해 `Seoul=PSAR`, `Oregon=외부 OKX 전략 실험`으로 역할 재설계

→ [Project 01 상세](./psar_rsi_bot/README.md) · [장애 대응 기록](./psar_rsi_bot/docs/INCIDENT_RECOVERY.md) · [Terraform 실험](./infra/terraform/README.md)

## Project 02 | Kubernetes & IaC 학습 프로젝트

FastAPI 기반 MSA를 Minikube에서 배포·검증하고 Prometheus/Grafana/HPA를 구성했습니다. Terraform으로 VPC/EKS/ECR 구성을 작성해 `plan`까지 검증했으며, 실제 AWS EKS `apply`와 운영은 수행하지 않았습니다.

- Minikube, MSA, HPA, Prometheus/Grafana
- Terraform VPC/EKS/ECR 구성 및 plan 검증
- Kustomize dev/prod overlay는 Project 01의 PSAR 매니페스트 경험으로 별도 구분

→ [Project 02 상세](./k8s-msa/README.md)

## 프로젝트 범위와 기간

| 구분 | 사실 기준 |
|---|---|
| PSAR 프로젝트 최초 AWS EC2 배포 | 2025-12-22 |
| 프로젝트 경험 | 2026-09 기준 약 9개월 |
| 서울 운영 환경 | EC2 + systemd |
| Oregon 환경 | Terraform + Docker Compose 기반 이전·운영 실험 |
| Kubernetes 프로젝트 | 2026-07-27 ~ 2026-08-10, Minikube 로컬 검증 |
| EKS 범위 | Terraform 구성 작성 및 plan 검증, 실제 apply·운영 없음 |

> 전체 프로젝트 기간과 특정 인스턴스 또는 프로세스의 연속 가동 기간은 구분합니다. 가동·장애·복구 성과는 확인 가능한 기간과 사례 단위로만 설명합니다.

## 핵심 장애 대응

- 2025-12-22 systemd 장애: unit 경로 오타(`/etc/systmed`), 존재하지 않는 `bot_main.py` 참조, 실행 옵션 누락을 수정하고 `daemon-reload`와 재시작 후 `Active: active (running)` 확인
- systemd 재시작 간격: `RestartSec=10` (FastAPI 기동 약 5초 + 여유 5초)
- Binance API 401: Public IP 변경과 IP whitelist 불일치를 확인·수정한 뒤 Elastic IP와 startup 사전 검증 로직 추가
- Binance 400/minNotional: 2026-01-26 18:27:51 오류부터 18:31:03 정상 주문 재개까지 **단일 사례 3분 12초**
- Oregon Binance 451: 코드나 네트워크 설정 문제가 아닌 외부 서비스의 지역 제약으로 판단하고 서울=PSAR, Oregon=외부 OKX 전략 실험으로 역할 분리

## 비용 최적화

과거 월 4만원대였던 AWS 비용을 최근 약 6,000원으로 낮춰 약 85% 절감했습니다. AMI 백업 후 불필요한 EC2를 종료하고 Elastic IP를 정리했으며, Stop 상태에서도 EBS와 EIP 관련 비용이 남을 수 있음을 확인했습니다.

## 문서와 증빙

- [전체 포트폴리오 개요](./PORTFOLIO_README.md)
- [PSAR 운영 시스템 상세](./psar_rsi_bot/README.md)
- [장애 대응 기록](./psar_rsi_bot/docs/INCIDENT_RECOVERY.md)
- [Terraform 인프라 실험](./infra/terraform/README.md)
- [Kubernetes Minikube 프로젝트](./k8s-msa/README.md)

## Architecture

![AWS Architecture](psar_rsi_bot/docs/Architecture/psar_portfolio_aws_architecture.png)

## Tech Stack

- Cloud / IaC: AWS EC2, IAM, Security Group, Elastic IP, CloudWatch, Terraform
- Runtime / CI/CD: Linux, systemd, Python, FastAPI, GitHub Actions, SSH, rsync
- Observability: Prometheus, Grafana, CloudWatch Logs, Telegram
- Container / Orchestration: Docker, Docker Compose, Kubernetes(Minikube), Kustomize

## Contact

- Email: `gyeong1181@naver.com`

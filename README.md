# gyeong1181

실제로 운영되는 자동화 시스템을 직접 만들고, 배포와 모니터링까지 연결해 운영형 포트폴리오로 증명하는 예비 클라우드/DevOps 엔지니어입니다.

## Focus
- `Cloud Engineer`
- `DevOps Engineer`
- `Infra / Platform`

## What I Build
- Webhook 기반 서비스 실행기 (TradingView → FastAPI → Binance Futures)
- EC2 + systemd 기반 상시 구동 환경 (3+ months, 0% redeployment failure)
- GitHub Actions 기반 자동 배포 (SSH/rsync → systemd restart)
- Prometheus / Grafana / Telegram 기반 모니터링 + 자동 복구 정책
- Terraform 기반 인프라 코드화 (Seoul / Oregon 멀티 리전)
- 운영 로그 추적과 장애 대응 문서화 ([INCIDENT_RECOVERY](./psar_rsi_bot/docs/INCIDENT_RECOVERY.md))
- CloudWatch 기반 EC2 비용 최적화 자동 분석 스크립트
- Docker Compose → Kubernetes (Minikube) 마이그레이션

## Featured Project
### Automated Trading Executor
TradingView Webhook 신호를 받아 FastAPI 서버에서 검증하고, Binance Futures 주문을 실행하는 자동매매 실행기입니다.

- 현재 실거래: `SOLUSDT 단일 운용`
- 확장 가능성: `BTCUSDT` 재활성화로 다중 심볼 확장 가능
- 구성: `FastAPI`, `EC2`, `systemd`, `GitHub Actions`, `Prometheus`, `Grafana`, `Telegram`
- 장애 자동 복구: `systemd RestartSec` + `Grafana Alert Rules` (수동 개입 0 달성)
- 비용 최적화: `CloudWatch` 기반 인스턴스 분석 자동화 + HTML 리포트 생성
- 오케스트레이션: `Kubernetes (Minikube)` — `k8s/` 매니페스트 포함

프로젝트 보기:
- [전체 포트폴리오 개요 (운영 증빙 포함)](./PORTFOLIO_README.md)
- [PSAR 봇 기술 상세 (구현·배포·메트릭·K8s)](./psar_rsi_bot/README.md)
- [장애 대응 자동화 정책](./psar_rsi_bot/docs/INCIDENT_RECOVERY.md)

## System Architecture

![AWS Architecture](psar_rsi_bot/docs/Architecture/psar_portfolio_aws_architecture.png)

> TradingView Webhook → AWS EC2 FastAPI → Binance Futures 주문 실행 / Telegram 알림  
> Prometheus + Grafana 모니터링 스택, GitHub Actions CI/CD, SSM·CloudWatch·S3 연동

## Tech Stack
- Cloud: `AWS EC2`, `IAM`, `CloudWatch Logs`
- Runtime: `Python`, `FastAPI`, `systemd`
- Data: `SQLite`
- Observability: `Prometheus`, `Grafana`, `Telegram`
- IaC: `Terraform`
- CI/CD: `GitHub Actions`, `SSH`, `rsync`
- Container: `Docker`, `Docker Compose`
- Orchestration: `Kubernetes` (Minikube, kustomize dev/prod overlay)
- Integrations: `TradingView Webhook`, `Binance Futures API`

## Background
- 서울과학기술대학교 공과대학 기계자동차공학과 졸업
- 정규 실무 포지션 합류 전 단계에서, 실제 운영되는 자동화 시스템을 직접 설계·구축하며 클라우드/운영 역량을 포트폴리오와 운영 증빙으로 정리하고 있습니다.

## Contact
- Email: `gyeong1181@gmail.com`

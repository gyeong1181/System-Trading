# Terraform IaC

이 디렉터리는 현재 수동으로 운영 중인 자동매매 서버 구성을 Terraform으로 옮기기 위한 최소 실전형 골격입니다.

포함 범위:
- EC2 인스턴스
- 보안 그룹(SSH / HTTP / 선택적 모니터링 포트)
- IAM Role / Instance Profile
- Elastic IP
- 초기 부트스트랩용 `user_data` (Docker + Docker Compose 플러그인 설치)
- 다중 전략 Docker Compose 스택 파일 자동 생성 (`/opt/trading-stack`)
- AWS SSM Parameter Store 기반 env 자동 동기화 (`/usr/local/bin/sync-trading-env.sh`)

## 디렉터리
- `versions.tf`: Terraform / Provider 버전
- `variables.tf`: 입력 변수
- `main.tf`: 인프라 리소스
- `outputs.tf`: 출력값
- `user_data.sh.tftpl`: 초기 서버 부트스트랩
- `terraform.tfvars.example`: 예시 변수 파일

## 시작 방법
1. 예시 파일 복사
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. 값 수정
- `aws_region` (기본값: `us-west-2`)
- `key_name`
- `ssh_allowed_cidrs`
- 필요 시 `monitoring_allowed_cidrs`
- 다중 전략 이미지
  - `psar_rsi_image`
  - `okx_qqq_image`
  - `okx_xau_image`
- `enable_psar_container=true|false`
- 자동 기동 여부: `deploy_strategy_stack=true|false`
- SSM env 옵션
  - `use_ssm_env`
  - `ssm_parameter_prefix`
  - `ssm_kms_key_arn` (선택)

3. 실행
```bash
terraform init
terraform plan
terraform apply
```

## 다중 컨테이너 운영(PSAR + OKX QQQ + OKX XAU)
인스턴스 생성 후 아래가 자동 준비됩니다.
- `/opt/trading-stack/docker-compose.yml`
- `/opt/trading-stack/env/*.env` (placeholder)
- `/etc/systemd/system/trading-strategy-stack.service`
- `/etc/systemd/system/trading-env-sync.service`
- `/usr/local/bin/sync-trading-env.sh`

`deploy_strategy_stack=true`이고 필수 이미지가 채워진 경우:
- 인스턴스 부팅 직후 `docker compose up -d` 자동 실행

필수 이미지 규칙:
- `enable_psar_container=false`(기본): `okx_qqq_image`, `okx_xau_image`만 필요
- `enable_psar_container=true`: `psar_rsi_image`까지 포함 3개 모두 필요

PSAR 이미지 자동 빌드/푸시:
- GitHub Actions 워크플로우: `.github/workflows/docker-psar-image.yml`
- 기본 푸시 경로: `ghcr.io/gyeong1181/quant-fleet-core:latest`
- `main` 푸시 또는 수동 실행(`workflow_dispatch`) 시 자동 빌드/푸시

`deploy_strategy_stack=false`(기본)인 경우:
- 파일만 생성하고 자동 기동은 하지 않음
- 수동으로 env 채운 뒤 아래 실행:

```bash
cd /opt/trading-stack
docker compose pull
docker compose up -d
sudo systemctl enable --now trading-strategy-stack.service
```

주의:
- 기존 `psar_rsi_bot`가 systemd로 `8000` 포트를 사용 중이면, `psar_rsi` 컨테이너의 `8000:8000` 포트 매핑과 충돌할 수 있습니다.
- 이 경우 둘 중 하나를 선택해야 합니다.
  - 기존 systemd 기반 실행 유지 (컨테이너의 8000 포트 매핑 제거)
  - PSAR도 컨테이너로 전환 (기존 systemd 서비스 중지)

## SSM Parameter Store 키 경로 규칙
`ssm_parameter_prefix=/trading/prod` 기준:

- `/trading/prod/psar_rsi/EXECUTION_MODE`
- `/trading/prod/psar_rsi/TV_WEBHOOK_SECRET`
- `/trading/prod/psar_rsi/BINANCE_API_KEY`
- `/trading/prod/psar_rsi/BINANCE_API_SECRET`
- `/trading/prod/psar_rsi/TELEGRAM_BOT_TOKEN`
- `/trading/prod/psar_rsi/TELEGRAM_CHAT_ID`
- `/trading/prod/okx_qqq/OKX_API_KEY`
- `/trading/prod/okx_qqq/OKX_API_SECRET`
- `/trading/prod/okx_qqq/OKX_API_PASSPHRASE`
- `/trading/prod/okx_qqq/TELEGRAM_BOT_TOKEN` (optional)
- `/trading/prod/okx_qqq/TELEGRAM_CHAT_ID` (optional)
- `/trading/prod/okx_xau/OKX_API_KEY`
- `/trading/prod/okx_xau/OKX_API_SECRET`
- `/trading/prod/okx_xau/OKX_API_PASSPHRASE`
- `/trading/prod/okx_xau/TELEGRAM_BOT_TOKEN` (optional)
- `/trading/prod/okx_xau/TELEGRAM_CHAT_ID` (optional)

권장:
- 타입은 `SecureString`
- 키 변경 후 즉시 반영:

```bash
sudo systemctl restart trading-env-sync.service
sudo systemctl restart trading-strategy-stack.service
```

빠른 등록:
- `scripts/bootstrap-ssm-parameters.sh`로 초기 키값 일괄 등록 가능
- 파일 기반 일괄 등록:

```bash
cd infra/terraform
cp scripts/ssm-secrets.template.env scripts/ssm-secrets.local.env
# scripts/ssm-secrets.local.env에 실제 키 입력
chmod +x scripts/bootstrap-ssm-from-file.sh
AWS_REGION=us-west-2 SSM_PREFIX=/trading/prod ./scripts/bootstrap-ssm-from-file.sh scripts/ssm-secrets.local.env
```

PowerShell(Windows) 사용 시:
```powershell
cd infra/terraform
.\scripts\bootstrap-ssm-from-file.ps1 -EnvFile ".\scripts\ssm-secrets.local.env" -AwsRegion "us-west-2" -SsmPrefix "/trading/prod"
```

## 현재 상태
- Terraform `plan` 기준 신규 리소스 7개 생성 계획 검증 완료
- 현재 구성은 기존 수동 운영 서버를 대체하는 것이 아니라, 재현 가능한 신규 인프라를 코드로 만드는 단계

## 실무에서 왜 중요한가
- 수동으로 만들던 인프라를 코드로 재현 가능하게 만듭니다.
- 신규 서버 구축, 장애 복구, 환경 복제 시 같은 구성을 반복 재사용할 수 있습니다.
- 팀 단위로 인프라 변경 이력을 코드 리뷰와 Git으로 관리할 수 있습니다.
- 운영 서버를 바꾸거나 확장할 때 콘솔 클릭 실수를 줄일 수 있습니다.
- 테스트 환경, 스테이징, 신규 고객용 환경을 빠르게 분리 생성할 수 있습니다.

## 현재 의도
- 기존 수동 운영 인프라를 코드로 재현 가능하게 만들기
- 이후 Nginx, Docker Compose, CloudWatch Agent, systemd 배포 단계까지 점진적으로 추가하기

## 컷오버 전 백업(필수)
Terraform으로 새 인스턴스를 만들기 전, 기존 서버에서 아래 데이터를 백업하세요.

백업 대상:
- 앱 로그: `psar_rsi_bot/logs/*`
- 주문/상태 DB: `psar_rsi_bot/data/bot.db`
- 앱 환경파일: `psar_rsi_bot/.env` (있을 경우)
- 모니터링 설정/데이터:
  - `deploy/monitoring/docker-compose.monitoring.yml`
  - `deploy/monitoring/prometheus/prometheus.yml`
  - `deploy/monitoring/prometheus/data`
  - `deploy/monitoring/grafana/data`
  - `deploy/monitoring/grafana/provisioning`
- 전략 스택 파일:
  - `/opt/trading-stack/docker-compose.yml`
  - `/opt/trading-stack/env/*`
- systemd unit:
  - `/etc/systemd/system/psar_rsi_bot.service`
  - `/etc/systemd/system/trading-strategy-stack.service`
  - `/etc/systemd/system/trading-env-sync.service`

서버에서 1회 실행:
```bash
cd /home/ec2-user/systemTrading/infra/terraform/scripts
bash backup-before-cutover.sh
```

S3에도 올리려면:
```bash
S3_URI=s3://<your-bucket>/trading-backups bash backup-before-cutover.sh
```

결과물:
- `/home/ec2-user/backups/trading_backup_YYYYmmdd_HHMMSS.tar.gz`

## 인스턴스 교체 시 주의
- `terraform apply`는 새 인스턴스를 즉시 생성할 수 있습니다.
- 기존 인스턴스는 **새 인스턴스 검증 완료 후** 삭제하세요.
- Terraform은 인프라를 만들고 지우지만, 로그/DB 같은 운영 데이터는 자동 이관하지 않습니다.

권장 순서:
1. 기존 서버 백업
2. Terraform으로 신규 서버 생성
3. 신규 서버 헬스체크/웹훅/주문/알림 검증
4. DNS/엔드포인트 전환
5. 기존 서버 종료 또는 `terraform destroy`

## CI/CD 반영 범위
- GitHub Actions가 있다고 해서 새 서버에 자동 반영되는 것은 아닙니다.
- 자동 반영하려면 워크플로우에 "신규 서버 배포 단계(SSH/SSM/Runner)"가 있어야 합니다.
- 현재 구성에서 자동화된 것은:
  - PSAR Docker 이미지 빌드/푸시(GHCR)
- 신규 서버 반영은 다음 중 하나를 추가해야 자동화됩니다.
  - self-hosted runner를 새 서버에 등록
  - GitHub Actions에서 SSH/SSM으로 `docker compose pull && up -d` 실행

## 다음 확장
- Route53 / 도메인
- ALB / HTTPS
- SSM Parameter Store / Secrets 연동
- CloudWatch Agent 상세 설정
- 기존 수동 생성 리소스 `terraform import`
- 앱 코드 배포와 `.env` 반영 자동화
- MT5 전략 컨테이너 추가(동일 Compose 스택 확장)

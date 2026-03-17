# Operations Checklist

이 문서는 현재 프로젝트의 운영 경로를 두 갈래로 나눠 정리한다.

- `서울`: 포트폴리오용 PSAR 운영 시스템
- `오리건`: Terraform 기반 외부 OKX 전략 멀티 컨테이너 서버

---

## 1. 로컬 사전 점검

로컬 PowerShell:

```powershell
cd "D:\코딩\자동매매\AI 자동매매 제작 프로젝트"
git status --short
```

변경사항이 있으면:

```powershell
git add .
git commit -m "describe change"
git push origin main
```

GitHub Actions 완료 후 서버를 만지는 편이 안전하다.

---

## 2. 오리건 Terraform 서버 점검

로컬 PowerShell:

```powershell
cd "D:\코딩\자동매매\AI 자동매매 제작 프로젝트\infra\terraform"
terraform output -raw public_ip
```

SSH timeout이면 현재 공인 IP를 다시 반영:

```powershell
$MYIP = (Invoke-RestMethod "https://checkip.amazonaws.com").Trim()
notepad .\terraform.tfvars
terraform plan -out tfplan
terraform apply tfplan
```

접속:

```powershell
$IP = terraform output -raw public_ip
ssh-keygen -R $IP
ssh -i "$env:USERPROFILE\sshkeys\key_oregon.pem" ec2-user@$IP
```

---

## 3. 오리건 런타임 점검

오리건 EC2:

```bash
sudo cloud-init status --wait
sudo systemctl status trading-env-sync.service --no-pager -l
cd /opt/trading-stack
sudo docker compose ps
sudo docker compose logs --tail 100
```

이미지 개별 검증:

```bash
sudo docker pull exitant/autotrade-app-okx-nasdaq:latest
sudo docker pull exitant/autotrade-app-okx-2.0-gold:latest
```

GHCR private pull이 필요하면:

```bash
echo 'REAL_GHCR_PAT' | sudo docker login ghcr.io -u gyeong1181 --password-stdin
sudo docker pull ghcr.io/gyeong1181/quant-fleet-core:latest
```

---

## 4. SSM 비밀값 반영

로컬 PowerShell에서 `infra/terraform/scripts/ssm-secrets.local.env` 수정 후:

```powershell
cd "D:\코딩\자동매매\AI 자동매매 제작 프로젝트\infra\terraform"
.\scripts\bootstrap-ssm-from-file.ps1 -EnvFile ".\scripts\ssm-secrets.local.env" -AwsRegion "us-west-2" -SsmPrefix "/trading/prod"
```

오리건 EC2:

```bash
sudo systemctl restart trading-env-sync.service
cd /opt/trading-stack
sudo docker compose up -d --force-recreate
```

---

## 5. 서울 포트폴리오 서버 점검

서울 EC2:

```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot
sudo systemctl status psar_rsi_bot --no-pager -l
sudo journalctl -u psar_rsi_bot -n 100 --no-pager
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics | head
```

Webhook 도달 확인:

```bash
sudo journalctl -u psar_rsi_bot -f
```

서울 서버를 다시 살릴 때는 별도 문서 참조:
- [seoul_portfolio_recovery_checklist.md](seoul_portfolio_recovery_checklist.md)

---

## 6. Grafana / Prometheus

서울 포트폴리오 서버 기준:

```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot/deploy/monitoring
docker compose -f docker-compose.monitoring.yml up -d
docker ps | grep -E "grafana|prometheus"
curl -s http://127.0.0.1:9090/-/healthy
curl -s http://127.0.0.1:3000/api/health
curl -s http://127.0.0.1:9090/api/v1/targets
```

---

## 7. 빠른 장애 분리 기준

- `ssh timeout`: 보안그룹의 현재 IP 허용 범위 확인
- `GHCR unauthorized`: 토큰 또는 package visibility 확인
- `docker compose pull` 전체 실패: 이미지별 `docker pull`로 분리
- `rejected_secret`: TradingView secret과 서버 env 불일치
- `451 from Binance Futures`: 코드 문제가 아니라 리전/거래소 제약
- `Grafana/Prometheus down`: 컨테이너, 포트, target 상태를 분리해서 확인

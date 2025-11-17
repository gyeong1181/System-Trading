# 배포 가이드

## 요구 사항

- Docker 24+
- AWS CLI 또는 gcloud CLI
- Terraform (선택)

## Docker 이미지 빌드

```bash
docker build -t full-option-signals:latest .
```

## AWS EC2 배포

1. Amazon Linux 2023 t3.medium 인스턴스를 생성하고 Docker를 설치합니다.
2. `.env` 와 `config.yaml` 을 `/opt/system-trading` 에 업로드합니다.
3. 다음 systemd 유닛을 `/etc/systemd/system/system-trading.service` 로 생성합니다.

   ```ini
   [Unit]
   Description=Full Option Signal Engine
   After=docker.service

   [Service]
   WorkingDirectory=/opt/system-trading
   ExecStart=/usr/bin/docker run --rm \
       --name system-trading \
       -v /opt/system-trading/logs:/app/logs \
       -v /opt/system-trading/config.yaml:/app/config.yaml \
       --env-file /opt/system-trading/.env \
       full-option-signals:latest
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

4. 서비스를 활성화합니다.

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now system-trading
   ```

## GCP Compute Engine 배포

1. Debian 12 e2-standard-2 인스턴스를 생성합니다.
2. Docker와 Cloud Monitoring 에이전트를 설치합니다.
3. `/etc/systemd/system/system-trading.service` 에 동일한 유닛 파일을 배치합니다.
4. `gcloud compute scp` 로 `config.yaml`, `.env`, `external_metrics.yaml` 을 전송합니다.
5. `sudo systemctl enable --now system-trading` 으로 실행합니다.

## Grafana 대시보드

1. `ops/grafana/dashboard.json` 을 Grafana UI 또는 provisioning 디렉터리에 업로드합니다.
2. Prometheus 와 Postgres 데이터 소스가 연결되어 있어야 합니다.
3. `signals` 테이블은 `logs/signals.csv` 를 ETL 로 적재하거나 TimescaleDB/BigQuery 등으로 파이프라인을 구성합니다.

## 백테스트/리플레이

```bash
python -m project.backtest.runner logs/signals.csv
```

또는 파이썬 인터프리터에서 `run_replay(Path("logs/signals.csv"))` 를 호출해 누적 성과를 확인합니다.

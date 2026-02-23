# Monitoring Stack (Prometheus + Grafana)

목표:
- 실거래 봇 상태를 실시간 시각화
- 장애 징후를 빠르게 감지
- 포트폴리오 증빙(운영 대시보드) 확보

## 1) 시작 명령어
```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot/deploy/monitoring
docker compose -f docker-compose.monitoring.yml up -d
```

확인:
```bash
docker ps | grep -E "psar_rsi_prometheus|psar_rsi_grafana"
curl -s http://127.0.0.1:9090/-/healthy
curl -s http://127.0.0.1:3000/api/health
curl -s http://127.0.0.1:8000/metrics | head
```

접속:
- Prometheus: `http://<EC2_PUBLIC_IP>:9090`
- Grafana: `http://<EC2_PUBLIC_IP>:3000`
- 기본 계정: `admin / admin123!`

## 2) 자동 로딩되는 항목
- Prometheus datasource (`uid=prometheus`)
- Dashboard: `PSAR RSI Bot - Ops Overview`

## 3) Grafana Alert Rule (UI에서 5분 설정)
Grafana UI:
- Alerting -> Alert rules -> New alert rule

Rule 1:
- Name: `Webhook_No_Traffic_10m`
- Query: `sum(increase(webhook_received_total[10m]))`
- Condition: `IS BELOW 1`
- For: `10m`

Rule 2:
- Name: `Order_Error_15m`
- Query: `sum(increase(order_result_total{status="error"}[15m]))`
- Condition: `IS ABOVE 0`
- For: `1m`

Rule 3:
- Name: `Binance_401_5m`
- Query: `sum(increase(binance_api_error_total{status_code="401"}[5m]))`
- Condition: `IS ABOVE 0`
- For: `1m`

Rule 4:
- Name: `Telegram_Failure_15m`
- Query: `sum(increase(telegram_send_fail_total[15m]))`
- Condition: `IS ABOVE 0`
- For: `1m`

## 4) Telegram Contact Point (UI)
Grafana UI:
- Alerting -> Contact points -> New contact point -> Telegram
- Bot token, Chat ID 입력
- Test 실행

## 5) 운영 팁
- 봇이 systemd로 실행 중이면 Prometheus target은 `host.docker.internal:8000` 그대로 사용
- 봇을 Docker로 실행하면 target을 컨테이너 DNS로 수정 필요

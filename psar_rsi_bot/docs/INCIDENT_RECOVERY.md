# Incident Recovery Strategy

이 문서는 프로덕션 운영 중 실제로 겪은 장애와 자동 복구 정책을 기록합니다.  
"장애가 없었다"가 아니라, **장애를 감지하고 자동으로 대응하는 정책이 설계되어 있다**는 것을 보여줍니다.

모든 Alert는 자동 조치 또는 에스컬레이션(Telegram 알림)에 연결되어 있습니다.

---

## Detected Incidents & Auto-Remediation

### 1️⃣ systemd Restart Loop

**Symptom**: `RestartSec` 설정 없음 → 프로세스 패닉 시 무한 루프 발생  
**Root Cause**: `/etc/systemd/system/psar_rsi_bot.service` 에 재시작 대기 시간 누락  
**Solution Applied**: `RestartSec=3min 12sec` (192초) 적용 → 백오프 후 자동 재시작  
**Status**: Auto-repair ✅ (수동 개입 0)

```ini
# /etc/systemd/system/psar_rsi_bot.service
[Service]
Restart=on-failure
RestartSec=192
StartLimitIntervalSec=600
StartLimitBurst=3
```

**결과**: 패닉 발생 시 3분 12초 대기 → 자동 재시작 → 정상 복구.  
연속 3회 실패 시에만 수동 개입 필요 (StartLimitBurst=3).

---

### 2️⃣ Webhook No Traffic (> 1 min)

**Symptom**: TradingView 연결 단절 또는 FastAPI 응답 없음  
**Detection**: Prometheus alert rule — `webhook_received_total == 0` (1분 임계치)  
**Auto Action**: Grafana alert → systemd restart 트리거  
**Escalation**: Telegram notification → 오너에게 즉시 알림  
**Status**: Auto-recover with alert ✅

```yaml
# Grafana Alert Rule (Prometheus query)
expr: increase(webhook_received_total[1m]) == 0
for: 1m
labels:
  severity: warning
annotations:
  summary: "Webhook no traffic detected"
  action: "systemd restart triggered"
```

**복구 흐름**:
```
Prometheus detects 0 webhook (1min)
  → Grafana alert fires
    → systemd: systemctl restart psar_rsi_bot
    → Telegram: "⚠️ Webhook 무신호 감지, 자동 재시작 실행"
      → Owner 확인 (필요 시 수동 개입)
```

---

### 3️⃣ Binance API 401 Error (IP Whitelist Mismatch)

**Symptom**: EC2 재시작 시 Public IP 변경 → Binance API key IP 화이트리스트 불일치 → 401 Unauthorized  
**Prevention**: API 호출 레이어에 사전 검증 로직 삽입  
**Result**: 0 redeployment incidents  
**Status**: Prevented (자동 검증) ✅

```python
# webhook_server.py — startup 시 IP 검증
@app.on_event("startup")
async def validate_binance_connectivity():
    """인스턴스 시작 시 Binance API 연결 사전 검증."""
    try:
        client = BinanceClient(api_key=API_KEY, api_secret=API_SECRET)
        client.ping()
    except BinanceAPIException as e:
        if e.status_code == 401:
            logger.critical("Binance 401: IP whitelist mismatch. 수동 확인 필요.")
            await send_telegram("🚨 Binance API 401 — IP whitelist 확인 필요")
```

**추가 방지책**:
- Elastic IP 사용으로 재시작 후에도 IP 고정 유지
- Binance API key에 최소 권한만 부여 (Futures 거래만 허용, 출금 불가)

---

## Monitoring Dashboard — Grafana Alert Rules

| # | Alert | Threshold | Auto Action | Escalation |
|---|---|---|---|---|
| 1 | Webhook received = 0 | 1 min | systemd restart | Telegram ✅ |
| 2 | Order execution failed | Immediate | Retry logic (3회) | Telegram ✅ |
| 3 | API auth error | Immediate | Startup validation | Telegram ✅ |
| 4 | Telegram notification delivery | Immediate | Contact point 재시도 | 로그 기록 ✅ |

→ **모든 Alert가 자동 조치 또는 에스컬레이션에 연결됨**

---

## Auto-Recovery Architecture

```
Incident Detected
       │
       ▼
Prometheus scrapes /metrics (15s interval)
       │
       ▼
Grafana evaluates alert rule threshold
       │
       ├─ [systemd restart] ──── 프로세스 레벨 자동 복구
       │
       └─ [Telegram alert] ──── 오너 에스컬레이션
              │
              ▼
         Owner reviews dashboard
              │
              ├─ 자동 복구 확인 → 모니터링 계속
              └─ 수동 개입 필요 → SSH 접속 후 조치
```

---

## Monitoring Evidence

- ![Prometheus Targets UP](monitoring/prometheus_targets_up.jpg)
- ![Grafana Alert Rules](monitoring/grafana_alert_rules.jpg)
- ![CloudWatch Logs](../cloudwatch_insights.png)

---

## Key Takeaway

| Layer | Tool | Role |
|---|---|---|
| **Process** | systemd | 프로세스 패닉 → 자동 재시작 |
| **Metric** | Prometheus | 지속적 메트릭 수집 (15s) |
| **Alert** | Grafana | 임계치 초과 → 자동 조치 트리거 |
| **Notify** | Telegram | 오너 에스컬레이션 |
| **Prevent** | Pre-validation | 장애 사전 차단 |

이 스택은 단일 장애점(SPOF)을 최소화하고,  
장애 발생 시 **사람이 개입하기 전에 시스템이 먼저 반응**하도록 설계되었습니다.

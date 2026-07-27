# Kubernetes Runbook — PSAR Trading System

이 문서는 `k8s/` 매니페스트를 Minikube 환경에서 실제로 실행하는 가이드입니다.  
포트폴리오 목적: "K8s 매니페스트 작성 + 실제 구동 경험"을 증명합니다.

---

## 전제 조건

```bash
# 설치 확인
minikube version   # v1.32.0 이상
kubectl version    # v1.28 이상
docker version     # 20.10 이상
```

설치가 안 되어 있다면:
- [Minikube 설치](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl 설치](https://kubernetes.io/docs/tasks/tools/)

---

## 1. 클러스터 시작

```bash
# Minikube 시작 (메모리 4GB, CPU 2코어 권장)
minikube start --memory=4096 --cpus=2

# 상태 확인
minikube status
kubectl cluster-info
```

---

## 2. 이미지 빌드 (Minikube 내부 Docker 사용)

```bash
# Minikube Docker 환경으로 전환 (이 터미널 세션에서만 적용)
eval $(minikube docker-env)   # Linux/Mac
# Windows PowerShell: & minikube -p minikube docker-env --shell powershell | Invoke-Expression

# 이미지 빌드
cd psar_rsi_bot
docker build -t psar-trading-bot:latest .

# 빌드 확인
docker images | grep psar
```

---

## 3. 네임스페이스 생성

```bash
kubectl create namespace trading
kubectl get namespaces
```

---

## 4. Secrets 준비

```bash
# 실제 값으로 시크릿 생성 (secrets.yaml의 placeholder 대신 직접 생성)
kubectl create secret generic trading-secrets \
  --namespace=trading \
  --from-literal=BINANCE_API_KEY=your-api-key \
  --from-literal=BINANCE_API_SECRET=your-api-secret \
  --from-literal=TELEGRAM_BOT_TOKEN=your-bot-token \
  --from-literal=TELEGRAM_CHAT_ID=your-chat-id \
  --from-literal=GRAFANA_ADMIN_PASSWORD=admin \
  --from-literal=WEBHOOK_SECRET=your-webhook-secret \
  --from-literal=SLACK_WEBHOOK_URL=""

# 확인
kubectl get secret trading-secrets -n trading
```

---

## 5. 배포 실행

### 기본 (base)
```bash
kubectl apply -k psar_rsi_bot/k8s/

# 또는 overlays 사용
kubectl apply -k psar_rsi_bot/k8s/overlays/dev    # dev 환경
kubectl apply -k psar_rsi_bot/k8s/overlays/prod   # prod 환경
```

### 상태 확인
```bash
# Pod 상태
kubectl get pods -n trading -w

# 서비스 상태
kubectl get services -n trading

# 이벤트 (오류 확인)
kubectl get events -n trading --sort-by='.lastTimestamp'
```

---

## 6. 접속 확인

```bash
# FastAPI 앱 (NodePort 30800)
minikube service psar-trading-bot -n trading

# 직접 URL 확인
minikube ip   # 예: 192.168.49.2
curl http://$(minikube ip):30800/health

# Grafana (NodePort 30300)
minikube service grafana -n trading
```

---

## 7. 로그 확인

```bash
# FastAPI 앱 로그
kubectl logs -n trading -l app=psar-trading-bot -f

# Prometheus 로그
kubectl logs -n trading -l app=prometheus -f

# Grafana 로그
kubectl logs -n trading -l app=grafana -f
```

---

## 8. Probe 동작 확인

```bash
# Liveness/Readiness 상태 확인
kubectl describe pod -n trading -l app=psar-trading-bot | grep -A 10 "Liveness\|Readiness\|Conditions"
```

**정상 출력 예시:**
```
Liveness:   http-get http://:8000/health delay=15s timeout=5s period=30s #success=1 #failure=3
Readiness:  http-get http://:8000/health delay=10s timeout=3s period=10s #success=1 #failure=3
Conditions:
  Ready: True
```

---

## 9. dev vs prod 차이 확인

```bash
# dev 배포 확인 (TRADING_MODE=PAPER, 리소스 축소)
kubectl apply -k psar_rsi_bot/k8s/overlays/dev
kubectl get deployment -n trading -o yaml | grep -A 5 "resources\|TRADING_MODE"

# prod 배포 (replicas=2, TRADING_MODE=LIVE)
kubectl apply -k psar_rsi_bot/k8s/overlays/prod
kubectl get pods -n trading   # 2개 Pod 확인
```

---

## 10. 정리

```bash
# 리소스 삭제
kubectl delete -k psar_rsi_bot/k8s/

# Minikube 정지 (삭제 아님)
minikube stop

# Minikube 완전 삭제
minikube delete
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImagePullBackOff` | Minikube Docker 환경 미설정 | `eval $(minikube docker-env)` 후 재빌드 |
| `CrashLoopBackOff` | 환경변수 누락 | `kubectl logs` 확인, Secret 점검 |
| Probe 실패 | `/health` 엔드포인트 없음 | `webhook_server.py`에 `/health` 라우트 확인 |
| PVC Pending | StorageClass 없음 | `minikube addons enable default-storageclass` |

---

## 포트폴리오 증빙 체크리스트

- [ ] `minikube start` 후 `kubectl get nodes` — Ready 상태 스크린샷
- [ ] `kubectl get pods -n trading` — 모든 Pod Running 스크린샷
- [ ] `curl http://$(minikube ip):30800/health` — 200 OK 응답 스크린샷
- [ ] `kubectl describe pod ... | grep Liveness` — Probe 설정 스크린샷
- [ ] Grafana 대시보드 접속 화면 스크린샷

---

## Daily Commands — 운영 중 자주 쓰는 명령어

> 아래 예시의 Pod명은 실제 환경에서 `kubectl get pods -n trading` 으로 확인 후 교체하세요.  
> 예: `dev-psar-trading-bot-7d9f4b8c6-xk2lp`

---

### 1. 실시간 로그 조회

**설명**: 실행 중인 Pod의 로그를 스트리밍으로 출력한다. `-f` 없으면 현재까지 누적 로그만 출력.

```bash
kubectl logs -n trading -l app=psar-trading-bot -f
# 특정 Pod 지정
kubectl logs -n trading dev-psar-trading-bot-7d9f4b8c6-xk2lp -f
```

**출력 예시:**
```
2026-07-27 10:05:01 [INFO] FastAPI started on 0.0.0.0:8000
2026-07-27 10:05:12 [INFO] Webhook received: SOLUSDT BUY
2026-07-27 10:05:13 [INFO] Order executed: qty=0.5, price=168.2
```

**언제 쓰는지**: 오더 실행 확인, 에러 추적, 실시간 모니터링.

---

### 2. Pod 상태 상세 조회

**설명**: Pod의 이벤트·Probe 결과·재시작 원인 등 전체 상태를 출력한다. 오류 첫 진단에 필수.

```bash
kubectl describe pod -n trading dev-psar-trading-bot-7d9f4b8c6-xk2lp
```

**출력 예시 (핵심 부분):**
```
Conditions:
  Ready:          True
Liveness:   http-get http://:8000/health  period=30s  #failure=3
Readiness:  http-get http://:8000/health  period=10s  #failure=3
Events:
  Normal   Started   2m    kubelet  Started container psar-trading-bot
  Warning  Unhealthy 30s   kubelet  Liveness probe failed: connection refused
```

**언제 쓰는지**: CrashLoopBackOff, Probe 실패, 이미지 풀 오류 원인 파악.

---

### 3. 배포 진행 상태 확인

**설명**: `kubectl apply` 후 롤링 업데이트가 완료됐는지 블로킹 상태로 대기·출력한다.

```bash
kubectl rollout status deployment/dev-psar-trading-bot -n trading
```

**출력 예시:**
```
Waiting for deployment "dev-psar-trading-bot" rollout to finish: 1 of 2 updated replicas are available...
deployment "dev-psar-trading-bot" successfully rolled out
```

**언제 쓰는지**: CI/CD 파이프라인에서 배포 성공 여부 자동 판별, 새 이미지 배포 후 확인.

---

### 4. 롤백 (이전 버전으로 되돌리기)

**설명**: 배포가 실패하거나 장애가 발생했을 때 즉시 이전 ReplicaSet으로 되돌린다.

```bash
# 즉시 롤백
kubectl rollout undo deployment/dev-psar-trading-bot -n trading

# 특정 revision으로 롤백
kubectl rollout history deployment/dev-psar-trading-bot -n trading
kubectl rollout undo deployment/dev-psar-trading-bot --to-revision=2 -n trading
```

**출력 예시:**
```
deployment.apps/dev-psar-trading-bot rolled back
```

**언제 쓰는지**: 새 버전 배포 후 오더 실행 오류 발생, 장애 즉시 복구가 필요할 때.

---

### 5. Pod 내부 접근 (셸 접속)

**설명**: 실행 중인 컨테이너 내부에 bash로 직접 접속한다. Docker의 `exec -it` 와 동일.

```bash
kubectl exec -it -n trading dev-psar-trading-bot-7d9f4b8c6-xk2lp -- /bin/bash
# bash 없으면
kubectl exec -it -n trading dev-psar-trading-bot-7d9f4b8c6-xk2lp -- /bin/sh
```

**출력 예시:**
```
root@dev-psar-trading-bot-7d9f4b8c6-xk2lp:/app#
# 내부에서 확인
ls logs/
cat logs/trading.log | tail -20
python -c "import webhook_server; print('OK')"
```

**언제 쓰는지**: 환경변수 확인(`env`), 파일 존재 여부, DB 연결 테스트, 의존성 검증.

---

### 6. 실시간 Pod 상태 모니터링

**설명**: Pod 목록을 실시간으로 갱신하며 출력한다. 배포·재시작 과정을 눈으로 확인.

```bash
kubectl get pods -n trading -w
```

**출력 예시:**
```
NAME                                      READY   STATUS              RESTARTS   AGE
dev-psar-trading-bot-7d9f4b8c6-xk2lp     0/1     ContainerCreating   0          3s
dev-psar-trading-bot-7d9f4b8c6-xk2lp     1/1     Running             0          12s
dev-prometheus-0                          1/1     Running             0          45s
dev-grafana-0                             1/1     Running             0          45s
```

**언제 쓰는지**: `kubectl apply` 직후 Pod가 정상 기동되는지 대기, 자동복구 과정 관찰.

---

### 7. Pod 강제 삭제 → 자동복구 테스트

**설명**: Pod를 강제로 지워서 Deployment의 자동복구(self-healing)가 작동하는지 검증한다.

```bash
kubectl delete pod -n trading dev-psar-trading-bot-7d9f4b8c6-xk2lp
# 바로 확인 (새 Pod가 자동 생성됨)
kubectl get pods -n trading -w
```

**출력 예시:**
```
pod "dev-psar-trading-bot-7d9f4b8c6-xk2lp" deleted
# 곧바로 새 Pod 생성
dev-psar-trading-bot-7d9f4b8c6-mn9qr     0/1     ContainerCreating   0          2s
dev-psar-trading-bot-7d9f4b8c6-mn9qr     1/1     Running             0          11s
```

**언제 쓰는지**: "K8s가 정말 자동복구 되나?" 포트폴리오 시연·면접 데모. StatefulSet은 같은 이름으로 재생성됨.

---

### 8. 리소스 사용량 확인

**설명**: 각 Pod의 실시간 CPU·Memory 사용량을 출력한다. Metrics Server가 필요.

```bash
# Minikube에서 Metrics Server 활성화 (최초 1회)
minikube addons enable metrics-server

# 사용량 확인
kubectl top pods -n trading
kubectl top nodes
```

**출력 예시:**
```
NAME                                    CPU(cores)   MEMORY(bytes)
dev-psar-trading-bot-7d9f4b8c6-xk2lp   8m           94Mi
dev-prometheus-0                        45m          210Mi
dev-grafana-0                           12m          87Mi
```

**언제 쓰는지**: Resource limits 적절성 검증, OOMKilled 원인 파악, 비용 최적화 판단 근거.

---

## 명령어 빠른 참조표

| 명령어 | 목적 |
|---|---|
| `kubectl logs -n trading -l app=X -f` | 실시간 로그 |
| `kubectl describe pod -n trading <pod>` | 상태·이벤트 상세 |
| `kubectl rollout status deployment/X -n trading` | 배포 완료 대기 |
| `kubectl rollout undo deployment/X -n trading` | 즉시 롤백 |
| `kubectl exec -it -n trading <pod> -- /bin/bash` | 컨테이너 내부 접속 |
| `kubectl get pods -n trading -w` | 실시간 Pod 모니터링 |
| `kubectl delete pod -n trading <pod>` | 자동복구 테스트 |
| `kubectl top pods -n trading` | CPU·Memory 사용량 |

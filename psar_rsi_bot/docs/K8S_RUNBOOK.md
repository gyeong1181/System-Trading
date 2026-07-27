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

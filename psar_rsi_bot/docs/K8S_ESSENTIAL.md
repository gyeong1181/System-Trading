# K8s 핵심 개념 — 면접 대비 정리

이 문서는 "K8s를 써봤다"고 말할 때 반드시 설명할 수 있어야 하는 개념만 담습니다.  
모든 설명은 면접 질문 기준으로 작성했습니다.

---

## 1. Pod vs Docker Container

### 한 줄 정의

| | |
|---|---|
| **Docker Container** | 하나의 프로세스를 격리해서 실행하는 단위 |
| **Pod** | K8s에서 컨테이너를 감싸는 최소 배포 단위. 1개 이상의 컨테이너를 묶는다 |

### 핵심 차이

| 항목 | Docker Container | Pod |
|---|---|---|
| 실행 주체 | Docker 데몬 | Kubernetes |
| 네트워크 | 컨테이너마다 별도 IP | Pod 내 컨테이너들이 IP 공유 (`localhost`로 통신) |
| 스토리지 | 컨테이너 내부 or 볼륨 직접 마운트 | Pod 단위로 Volume을 정의, 안의 컨테이너들이 공유 가능 |
| 생애주기 | 직접 관리 | K8s가 선언된 상태(desired state)에 맞게 자동 관리 |
| 재시작 | `--restart=always` 등 플래그 | Deployment/StatefulSet이 재시작 정책 관리 |
| 스케일 | `docker run` 여러 번 | `replicas: N` 한 줄로 N개 유지 |

### 면접 질문 예시

> "Pod 안에 컨테이너를 여러 개 넣는 건 언제 하나요?"

→ **Sidecar 패턴**. 예: FastAPI 앱 컨테이너 + 로그 수집 컨테이너를 같은 Pod에 넣으면 로그 파일을 공유 볼륨으로 읽을 수 있다. 이 프로젝트에서는 단일 컨테이너 Pod를 사용했다.

---

## 2. Liveness vs Readiness Probe

### 한 줄 정의

| | |
|---|---|
| **Liveness** | "앱이 살아있나?" → 실패하면 컨테이너를 **재시작** |
| **Readiness** | "앱이 트래픽 받을 준비가 됐나?" → 실패하면 Service에서 **제외** (재시작 X) |

### 혼동하면 생기는 문제

```
잘못된 설정: Liveness에 DB 연결 체크를 넣음
  → DB가 순간 응답 느림
  → Liveness 실패
  → 컨테이너 재시작
  → 재시작 중에도 DB 느림
  → 또 재시작
  → CrashLoopBackOff (무한 루프)
```

**원칙**: Liveness는 **앱 자체**가 망가졌는지만 체크. 외부 의존성(DB, 외부 API)은 넣지 않는다.

### 동작 비교

| 상황 | Liveness | Readiness |
|---|---|---|
| 실패 시 동작 | 컨테이너 강제 재시작 | Service LB에서 해당 Pod 제외 |
| 성공 시 동작 | 아무것도 안 함 | Pod를 Service에 다시 포함 |
| 주 용도 | 행(hang) 걸린 앱 감지 | 배포 중 구버전→신버전 트래픽 전환 |
| 외부 의존성 포함 | ❌ 금지 | △ 상황에 따라 |

### 이 프로젝트 설정

```yaml
livenessProbe:
  httpGet:
    path: /health      # FastAPI 앱 자체 응답만 체크
    port: 8000
  initialDelaySeconds: 15  # 앱 기동 시간 15초 기다린 뒤 시작
  periodSeconds: 30         # 30초마다 체크
  failureThreshold: 3       # 3번 연속 실패 시 재시작

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10   # Liveness보다 5초 먼저 시작 (트래픽 조기 수신)
  periodSeconds: 10          # 더 자주 체크 (트래픽 전환 빠르게)
  failureThreshold: 3
```

### 면접 질문 예시

> "Liveness랑 Readiness 차이가 뭐예요?"

→ Liveness는 앱이 죽었을 때 재시작시키는 용도, Readiness는 앱이 준비되기 전에 트래픽이 들어오는 걸 막는 용도입니다. 두 개를 같은 엔드포인트로 설정하되, Readiness를 더 짧은 주기로 설정해 롤링 업데이트 시 신버전이 준비되는 즉시 트래픽이 넘어가도록 했습니다.

---

## 3. Deployment vs StatefulSet

### 한 줄 정의

| | |
|---|---|
| **Deployment** | 상태 없는(stateless) 앱을 N개 유지. Pod가 죽으면 새 Pod로 교체 |
| **StatefulSet** | 상태 있는(stateful) 앱 관리. Pod마다 고유 이름·고유 스토리지를 유지 |

### 선택 기준

```
이 앱을 재시작했을 때 "이전 데이터"가 필요한가?
  → YES: StatefulSet + PVC
  → NO:  Deployment
```

| 항목 | Deployment | StatefulSet |
|---|---|---|
| Pod 이름 | 랜덤 (`app-7d9f4b-xk2lp`) | 순번 고정 (`prometheus-0`, `prometheus-1`) |
| 스토리지 | 공유 볼륨 or emptyDir | Pod마다 개별 PVC (재시작해도 같은 PVC 재연결) |
| 스케일 아웃 | 순서 무관하게 동시 생성 | 0→1→2 순서대로 생성, N-1→N 순서대로 삭제 |
| 롤링 업데이트 | 동시 다수 교체 가능 | 역순(N부터)으로 하나씩 교체 |
| 사용 예 | FastAPI, nginx, REST API | Prometheus, Grafana, DB, Kafka |

### 이 프로젝트에서 선택 이유

```
FastAPI 봇 → Deployment
  이유: 주문 실행 코드는 상태가 없음. 재시작해도 Binance API로 현재 상태 조회 가능.
  SQLite DB는 현재 단일 파일로 볼륨에 마운트 (추후 PVC로 분리 가능).

Prometheus → StatefulSet
  이유: /prometheus 경로에 30일치 시계열 메트릭 데이터 누적.
  Pod 재시작 시 이 데이터가 사라지면 모니터링 히스토리 전체 소실.
  → PVC 5Gi로 데이터 영속성 보장.

Grafana → StatefulSet
  이유: 대시보드 설정, Alert 룰, 데이터소스 설정이 /var/lib/grafana에 저장.
  재시작마다 설정 초기화되면 운영 불가.
  → PVC 2Gi로 설정 영속성 보장.
```

### 면접 질문 예시

> "왜 Prometheus에 StatefulSet을 썼나요?"

→ Prometheus는 수집한 메트릭 데이터를 로컬 디스크에 저장합니다. Deployment로 배포하면 Pod 재시작 시 PVC가 새로 생성되어 히스토리가 날아갑니다. StatefulSet은 Pod 이름이 고정(`prometheus-0`)되어 재시작 후에도 동일한 PVC에 재연결되므로 데이터가 유지됩니다.

---

## 4. Kustomize Overlay Pattern

### 왜 쓰는가 — DRY 원칙

```
DRY = Don't Repeat Yourself (같은 것을 두 번 쓰지 않는다)

나쁜 방법:
  k8s-dev/deployment.yaml   ← 80% 동일한 내용
  k8s-prod/deployment.yaml  ← 80% 동일한 내용

  문제: deployment.yaml 하나 바꾸면 두 파일 모두 손으로 수정해야 함.

좋은 방법 (Kustomize):
  k8s/deployment.yaml        ← 공통 내용 한 번만 작성 (base)
  k8s/overlays/dev/          ← "dev에서 다른 부분만" 덮어씀 (patch)
  k8s/overlays/prod/         ← "prod에서 다른 부분만" 덮어씀 (patch)
```

### 구조

```
psar_rsi_bot/k8s/
├── deployment.yaml          ← base: 공통 설정 (이미지, probe, envFrom)
├── statefulset.yaml
├── service.yaml
├── configmap.yaml
├── secrets.yaml
└── kustomization.yaml       ← base 진입점

└── overlays/
    ├── dev/
    │   ├── kustomization.yaml   ← resources: ../../ (base 참조)
    │   └── patch-dev.yaml       ← replicas=1, PAPER모드, 리소스 축소
    └── prod/
        ├── kustomization.yaml   ← resources: ../../ (base 참조)
        └── patch-prod.yaml      ← replicas=2, LIVE모드, 리소스 확장
```

### dev vs prod 차이 — 이 프로젝트 기준

| 항목 | dev | prod |
|---|---|---|
| `TRADING_MODE` | `PAPER` (모의 거래) | `LIVE` (실거래) |
| `replicas` | 1 | 2 |
| CPU limit | 200m | 1000m |
| Memory limit | 256Mi | 1Gi |
| Image tag | `latest` (로컬 빌드) | `stable` (검증된 이미지) |
| Prometheus PVC | 1Gi | 20Gi |
| namePrefix | `dev-` | `prod-` |

### 실행 방법

```bash
# 어떤 리소스가 생성될지 미리 보기 (실제 적용 X)
kubectl kustomize psar_rsi_bot/k8s/overlays/dev

# dev 환경 배포
kubectl apply -k psar_rsi_bot/k8s/overlays/dev

# prod 환경 배포
kubectl apply -k psar_rsi_bot/k8s/overlays/prod
```

### 면접 질문 예시

> "환경별 설정 분리를 어떻게 했나요? Helm은 안 썼나요?"

→ Kustomize overlay 패턴을 사용했습니다. Helm은 템플릿 언어를 배워야 하는 진입 장벽이 있는 반면, Kustomize는 순수 YAML에 patch만 얹는 방식이라 구조가 단순합니다. base에 공통 설정을 두고, dev/prod overlay에서 replicas·리소스·환경변수만 JSON patch로 덮어씁니다. 변경 사항이 base에만 반영되면 두 환경에 동시 적용됩니다.

---

## 면접 빈출 질문 모음

| 질문 | 한 줄 답변 |
|---|---|
| Pod와 Container 차이는? | Pod는 K8s 최소 배포 단위, 1개 이상 컨테이너를 묶고 IP를 공유한다 |
| Liveness가 실패하면? | 컨테이너를 재시작한다 |
| Readiness가 실패하면? | Service에서 제외해 트래픽을 안 보낸다 (재시작은 안 한다) |
| StatefulSet을 쓰는 이유? | Pod마다 고유 PVC가 보장되어 재시작 후에도 데이터가 유지된다 |
| Kustomize와 Helm 차이? | Kustomize는 순수 YAML + patch, Helm은 템플릿 엔진. 단순 환경 분리엔 Kustomize가 적합 |
| `kubectl delete pod` 하면? | Deployment가 감지해 즉시 새 Pod를 생성한다 (self-healing) |
| `replicas: 0` 이면? | Pod가 전부 삭제된다. 비용 절감 목적으로 비활성화할 때 사용 |

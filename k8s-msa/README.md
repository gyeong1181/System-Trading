# msa-on-k8s

FastAPI 기반 5개 마이크로서비스를 Docker -> minikube -> AWS EKS 순으로 배포하는 프로젝트.

## Services

| service | port(local) | 역할 | K8s에서 증명하는 것 |
|---|---|---|---|
| user-service | 8001 | 회원가입 / JWT 로그인 | Secret 주입 |
| product-service | 8002 | 상품 조회 + Redis 캐시 | readinessProbe (의존성 장애 분리) |
| order-service | 8003 | 주문 오케스트레이션 | Service Discovery (내부 DNS) |
| payment-service | 8004 | 결제 승인 (장애/지연 시뮬레이션) | HPA (CPU 기반 오토스케일) |
| notification-service | 8005 | 알림 발송 로그 | stdout 로그 수집 |

## Quick start (local)

```powershell
.\build.ps1
docker compose up -d
.\smoke-test.ps1
```

## K8s 구조 (Phase 2)

```
k8s/
├── namespace.yaml
├── configmap.yaml          # 서비스 URL, Redis 연결, 환경 파라미터
├── secret.yaml             # JWT_SECRET (base64)
├── redis/
│   ├── statefulset.yaml    # PVC 1Gi — 캐시 데이터 영속
│   └── service.yaml        # ClusterIP
├── user-service/           # NodePort 30801 (로그인 API 외부 노출)
├── product-service/        # ClusterIP (order-service 내부 호출)
├── order-service/          # NodePort 30803 (주문 API 외부 노출)
├── payment-service/        # ClusterIP (결제 API 내부 전용)
├── notification-service/   # ClusterIP (알림 내부 전용)
└── kustomization.yaml      # kubectl apply -k k8s/ 진입점
```

**Service Discovery**: order-service → `http://payment-service.msa.svc.cluster.local:8000`  
**Probe 설계**: liveness=`/healthz`(앱 자체), readiness=`/readyz`(의존성 포함)

## Roadmap
- [x] Phase 1: Docker 이미지 5개 + compose 통합 테스트
- [x] Phase 2: Minikube 배포 (Deployment / Service / ConfigMap / Secret / Probe)
- [ ] Phase 3: PostgreSQL StatefulSet + PVC, Ingress
- [ ] Phase 4: EKS (Terraform) + ECR + LoadBalancer
- [ ] Phase 5: Prometheus + Grafana + HPA 부하 데모

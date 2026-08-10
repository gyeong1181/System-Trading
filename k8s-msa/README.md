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

## K8s 구조 (Phase 3)

```
k8s/
├── namespace.yaml
├── configmap.yaml          # 서비스 URL, Redis/DB 연결, 환경 파라미터
├── secret.yaml             # JWT_SECRET, POSTGRES_USER, POSTGRES_PASSWORD (base64)
├── ingress.yaml            # 경로 기반 라우팅: /api/users, /api/orders, /api/products
├── redis/
│   ├── statefulset.yaml    # PVC 1Gi — 캐시 데이터 영속
│   └── service.yaml        # ClusterIP
├── postgres/
│   ├── statefulset.yaml    # PVC 5Gi — 주문/결제 데이터 영속 (postgres:16-alpine)
│   └── service.yaml        # ClusterIP (내부 전용)
├── user-service/           # NodePort 30801 (로그인 API 외부 노출)
├── product-service/        # ClusterIP (order-service 내부 호출)
├── order-service/          # NodePort 30803 (주문 API 외부 노출)
├── payment-service/        # ClusterIP (결제 API 내부 전용)
├── notification-service/   # ClusterIP (알림 내부 전용)
└── kustomization.yaml      # kubectl apply -k k8s/ 진입점 (18개 리소스)
```

**Service Discovery**: order-service → `http://payment-service.msa.svc.cluster.local:8000`  
**DB 접근**: `postgres.msa.svc.cluster.local:5432` (ClusterIP 내부 전용)  
**Probe 설계**: liveness=`/healthz`(앱 자체), readiness=`/readyz`(의존성 포함)  
**Ingress**: `msa.local/api/users`, `msa.local/api/orders`, `msa.local/api/products` → 서비스 라우팅

## Minikube 실행 (Phase 3)

```powershell
# 1. 클러스터 시작 + Ingress 활성화
minikube start --memory=4096 --cpus=2
minikube addons enable ingress

# 2. Docker 이미지 빌드 (Minikube 내부 레지스트리)
& minikube docker-env --shell powershell | Invoke-Expression
.\build.ps1

# 3. Secret 주입
kubectl create secret generic msa-secret -n msa `
  --from-literal=JWT_SECRET=dev-jwt-secret `
  --from-literal=POSTGRES_USER=msauser `
  --from-literal=POSTGRES_PASSWORD=msapassword

# 4. 전체 배포
kubectl apply -k k8s/

# 5. 상태 확인
kubectl get all -n msa
kubectl get ingress -n msa
```

## 실행 스크린샷 (Phase 3 — Minikube)

**Pod 상태 확인** (`kubectl get pods -n msa`)

![Pod Running](docs/screenshots/kubectl%201.jpg)

**전체 리소스 + Ingress 확인** (`kubectl get all -n msa` / `kubectl get ingress -n msa`)

![All Resources & Ingress](docs/screenshots/kubectl%202%2C3.jpg)

> 7개 Pod 모두 `Running 1/1` · StatefulSet(postgres, redis) 정상 · Ingress IP `192.168.49.2` 배정 완료

## Terraform — AWS EKS 구성 (Phase 4)

```
terraform/
├── versions.tf    # Terraform >= 1.6, AWS provider ~> 5.0
├── variables.tf   # 리전(서울), 클러스터명, 노드 스펙, CIDR
├── main.tf        # VPC(3-AZ) + EKS 클러스터 + 관리형 노드그룹
├── ecr.tf         # 5개 서비스 ECR 리포지토리 + 이미지 보관 정책
└── outputs.tf     # 클러스터 엔드포인트, ECR URL, kubeconfig 명령어
```

```powershell
# 1. 초기화 (모듈 다운로드)
cd terraform
terraform init

# 2. 변경사항 미리 확인 (실제 AWS 리소스 생성 안 함)
terraform plan

# 3. 실제 배포 (AWS 비용 발생 — 포트폴리오는 plan까지만 권장)
terraform apply

# 4. kubectl EKS 연결
aws eks update-kubeconfig --region ap-northeast-2 --name msa-eks-cluster

# 5. 기존 K8s 매니페스트 그대로 배포
kubectl apply -k k8s/
```

**EKS 예상 비용** (실제 배포 시): 클러스터 ~$0.10/h + t3.medium 2대 ~$0.09/h × 2 = 약 **$200/월**  
포트폴리오 용도는 `terraform plan` 결과 스크린샷만으로 충분.

## Roadmap
- [x] Phase 1: Docker 이미지 5개 + compose 통합 테스트
- [x] Phase 2: Minikube 배포 (Deployment / Service / ConfigMap / Secret / Probe)
- [x] Phase 3: PostgreSQL StatefulSet + PVC, Ingress (경로 기반 라우팅)
- [x] Phase 4: EKS (Terraform IaC) + ECR + 노드그룹 구성
- [ ] Phase 5: Prometheus + Grafana + HPA 부하 데모

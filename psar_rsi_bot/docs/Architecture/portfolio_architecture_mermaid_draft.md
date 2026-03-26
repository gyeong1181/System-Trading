# Portfolio Architecture Mermaid Draft

이 문서는 포트폴리오용 시각화 아키텍처 초안이다.  
메인 다이어그램은 현재 최종 운영 구조를, 보조 다이어그램은 Oregon 이전 시도와 최종 구조 조정을 보여준다.

---

## 1. Current Operating Architecture

```mermaid
flowchart TB
    subgraph Seoul["Seoul Region | Portfolio Operation System"]
        TV[TradingView Alert]
        API[FastAPI Webhook Executor]
        DB[(SQLite)]
        BINANCE[Binance Futures]
        TG[Telegram Alerts]
        CW[CloudWatch Logs]
        PROM[Prometheus]
        GRAFANA[Grafana]
        GHA[GitHub Actions]
        SYSTEMD[systemd service]

        TV -->|POST /tv/webhook| API
        API --> DB
        API --> BINANCE
        API --> TG
        API --> CW
        API -->|/metrics| PROM
        PROM --> GRAFANA
        GHA -->|SSH / rsync deploy| SYSTEMD
        SYSTEMD --> API
    end

    subgraph Oregon["Oregon Region | External Strategy Zone"]
        TF[Terraform]
        SSM[AWS SSM Parameter Store]
        DC[Docker Compose]
        QQQ[OKX Nasdaq Container]
        XAU[OKX Gold Container]
        OKX[OKX Exchange]

        TF --> DC
        SSM --> DC
        DC --> QQQ
        DC --> XAU
        QQQ --> OKX
        XAU --> OKX
    end

    NOTE1["Decision: PSAR remains in Seoul"]
    NOTE2["Reason: Binance Futures blocked in Oregon (HTTP 451)"]
    NOTE3["Meaning: portfolio-grade ops in Seoul, vendor OKX stack separated"]

    Oregon --- NOTE1
    Oregon --- NOTE2
    Oregon --- NOTE3
```

---

## 2. Migration Attempt and Final Decision

```mermaid
flowchart LR
    A[Seoul Legacy PSAR\nsystemd + Grafana + Prometheus + live trading]
    B[Terraform to Oregon\nEC2 + IAM + SG + EIP + Docker bootstrap]
    C[Multi-container attempt\nPSAR + OKX Nasdaq + OKX Gold]
    D[Runtime issues review\nGHCR auth / compose / env / port mapping]
    E[Binance Futures blocked\nHTTP 451 in Oregon]
    F[Role split decision\nSeoul keeps PSAR\nOregon reduced to external OKX scope]
    G[Final portfolio message\nBuilt, operated, migrated, validated,\nand redesigned under constraints]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
```

---

## 3. Caption Draft

- 현재 프로젝트는 수익 자랑용 전략이 아니라, 운영 가능한 자동화 시스템을 직접 구축하고 배포·관측·분리 운영한 포트폴리오 자산이다.
- Terraform 기반 Oregon 이전과 멀티 컨테이너 운용을 실제로 시도했고, Binance 리전 제약과 vendor 환경 적합성을 확인한 뒤 구조를 다시 조정했다.
- 최종적으로 서울은 포트폴리오용 PSAR 운영 시스템, Oregon은 외부 전략 실험/운영 영역으로 역할을 분리했다.

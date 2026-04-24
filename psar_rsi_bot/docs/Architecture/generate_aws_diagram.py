"""
AWS Architecture Diagram – PSAR RSI Bot Portfolio System
실행: cd <repo-root> && python psar_rsi_bot/docs/Architecture/generate_aws_diagram.py
출력: psar_rsi_bot/docs/Architecture/psar_portfolio_aws_architecture.png
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import EC2Instance, EC2ElasticIpAddress
from diagrams.aws.network import InternetGateway
from diagrams.aws.management import CloudwatchLogs, SystemsManagerParameterStore
from diagrams.aws.storage import S3
from diagrams.aws.security import IAM
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.ci import GithubActions
from diagrams.saas.chat import Telegram
from diagrams.aws.general import InternetAlt1, Client, GenericOfficeBuilding

graph_attr = {
    "fontsize": "17",
    "bgcolor": "#FFFFFF",
    "pad": "1.8",
    "splines": "ortho",
    "nodesep": "0.9",
    "ranksep": "1.2",
    "fontname": "Arial",
    "dpi": "160",
    "concentrate": "false",
}

node_attr = {
    "fontsize": "11",
    "fontname": "Arial",
}

with Diagram(
    "PSAR RSI Bot  –  Portfolio AWS Architecture",
    filename="psar_rsi_bot/docs/Architecture/psar_portfolio_aws_architecture",
    outformat="png",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
):

    # ── 외부 입력 (최상단) ─────────────────────────────────────
    tradingview = InternetAlt1("TradingView\nWebhook Alert")

    # ── AWS Seoul Region ───────────────────────────────────────
    with Cluster("AWS  ap-northeast-2  (Seoul Region)"):

        # VPC / Subnet / EC2
        with Cluster("VPC  /  Public Subnet"):
            igw = InternetGateway("Internet\nGateway")
            eip = EC2ElasticIpAddress("Elastic IP")

            with Cluster("EC2  t3.small  ·  Amazon Linux 2023"):
                app = EC2Instance("FastAPI  (psar_rsi_bot)\nsystemd  ·  port 8000")

        # Monitoring Stack (Docker, EC2 위에서 동작하지만 시각적으로 분리)
        with Cluster("Monitoring Stack  (Docker Compose  ·  on EC2)"):
            prom    = Prometheus("Prometheus\n:9090")
            grafana = Grafana("Grafana\n:3000")

        # AWS 관리 서비스
        with Cluster("AWS Managed Services"):
            ssm     = SystemsManagerParameterStore("SSM\nParameter Store")
            cw_logs = CloudwatchLogs("CloudWatch\nLogs")
            s3      = S3("S3 Bucket\n(Nightly Backup)")

    # ── 외부 서비스 ────────────────────────────────────────────
    with Cluster("External Services"):
        binance  = GenericOfficeBuilding("Binance\nFutures API")
        telegram = Telegram("Telegram Bot")

    # ── CI/CD & 운영자 ─────────────────────────────────────────
    github = GithubActions("GitHub Actions\n(CI/CD Deploy)")
    user   = Client("운영자\n(Dashboard)")

    # ════════════════════════════════════════════════════════════
    # 연결선
    # ════════════════════════════════════════════════════════════

    # 1. TradingView → FastAPI (Webhook)
    tradingview >> Edge(
        label="HTTPS Webhook", color="darkorange", fontcolor="darkorange"
    ) >> igw >> Edge(color="darkorange") >> eip >> Edge(color="darkorange") >> app

    # 2. GitHub Actions → EC2 (배포)
    github >> Edge(
        label="SSH / rsync\nsystemctl restart",
        color="blueviolet", fontcolor="blueviolet", style="dashed"
    ) >> app

    # 3. FastAPI → Prometheus (메트릭 스크랩)
    app >> Edge(
        label="GET /metrics  (15s)",
        color="tomato", fontcolor="tomato"
    ) >> prom

    # 4. Prometheus → Grafana (시각화)
    prom >> Edge(
        label="쿼리",
        color="tomato", fontcolor="tomato"
    ) >> grafana

    # 5. 운영자 → Grafana (대시보드)
    user >> Edge(
        label="Browser  :3000",
        color="seagreen", fontcolor="seagreen"
    ) >> grafana

    # 6. FastAPI → Binance (주문 실행)
    app >> Edge(
        label="REST API  주문 실행",
        color="steelblue", fontcolor="steelblue"
    ) >> binance

    # 7. FastAPI → Telegram (체결·오류 알림)
    app >> Edge(
        label="체결 · 오류 알림",
        color="royalblue", fontcolor="royalblue"
    ) >> telegram

    # 8. Grafana → Telegram (Alert)
    grafana >> Edge(
        label="Grafana Alert",
        color="royalblue", style="dashed"
    ) >> telegram

    # 9. FastAPI → SSM (시크릿 조회)
    app >> Edge(
        label="시크릿 조회", color="dimgray", style="dashed", fontcolor="dimgray"
    ) >> ssm

    # 10. FastAPI → CloudWatch (로그)
    app >> Edge(
        label="로그 송신", color="dimgray", style="dashed", fontcolor="dimgray"
    ) >> cw_logs

    # 11. FastAPI → S3 (야간 백업)
    app >> Edge(
        label="cron 00:00  백업",
        color="dimgray", style="dashed", fontcolor="dimgray"
    ) >> s3

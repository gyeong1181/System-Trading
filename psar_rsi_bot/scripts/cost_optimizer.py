#!/usr/bin/env python3
"""
CloudWatch 기반 EC2 비용 최적화 자동 분석 스크립트.

주 1회 cron 실행 예시:
    0 9 * * 1 EC2_INSTANCE_ID=i-xxx python3 /app/scripts/cost_optimizer.py

이 스크립트는 분석·제안만 합니다. 실제 변경은 수동 승인 후 진행하세요.

필수 환경변수:
    EC2_INSTANCE_ID   - 분석 대상 인스턴스 ID
    AWS_DEFAULT_REGION - 리전 (기본: ap-northeast-2)

선택 환경변수:
    SLACK_WEBHOOK_URL  - Slack Incoming Webhook URL
    REPORT_DIR         - HTML 리포트 저장 경로 (기본: ./reports)
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import boto3
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
INSTANCE_ID = os.getenv("EC2_INSTANCE_ID", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
REPORT_DIR = Path(os.getenv("REPORT_DIR", "./reports"))
LOOKBACK_DAYS = 30
MONTHLY_HOURS = 720  # 30일 * 24시간

# ap-northeast-2 온디맨드 가격 (USD/시간, 2024 기준)
INSTANCE_PRICING = {
    "t3.nano":   {"vcpu": 2, "memory_gib": 0.5,  "hourly_usd": 0.0052},
    "t3.micro":  {"vcpu": 2, "memory_gib": 1.0,  "hourly_usd": 0.0104},
    "t3.small":  {"vcpu": 2, "memory_gib": 2.0,  "hourly_usd": 0.0208},
    "t3.medium": {"vcpu": 2, "memory_gib": 4.0,  "hourly_usd": 0.0416},
    "t3.large":  {"vcpu": 2, "memory_gib": 8.0,  "hourly_usd": 0.0832},
}

# ap-northeast-2 Spot 절감률 (온디맨드 대비 약 70%)
SPOT_DISCOUNT_RATE = 0.70


# ──────────────────────────────────────────────
# CloudWatch 데이터 수집
# ──────────────────────────────────────────────

def _get_metric(
    cw,
    instance_id: str,
    metric_name: str,
    statistic: str,
    period: int = 86400,
    namespace: str = "AWS/EC2",
) -> list[float]:
    """CloudWatch 메트릭 데이터포인트 리스트 반환."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=LOOKBACK_DAYS)

    resp = cw.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=period,
        Statistics=[statistic],
    )
    return [d[statistic] for d in resp.get("Datapoints", [])]


def collect_metrics(cw, instance_id: str) -> dict:
    """30일 CPU / 네트워크 평균·최대값 수집."""
    log.info("CloudWatch 메트릭 수집 중 (지난 %d일)...", LOOKBACK_DAYS)

    cpu_avg_series = _get_metric(cw, instance_id, "CPUUtilization", "Average")
    cpu_max_series = _get_metric(cw, instance_id, "CPUUtilization", "Maximum", period=3600)
    net_in_series = _get_metric(cw, instance_id, "NetworkIn", "Average")

    avg_cpu = round(sum(cpu_avg_series) / len(cpu_avg_series), 2) if cpu_avg_series else 0.0
    max_cpu = round(max(cpu_max_series), 2) if cpu_max_series else 0.0
    avg_net_in_bytes = round(sum(net_in_series) / len(net_in_series), 0) if net_in_series else 0.0

    log.info("  평균 CPU: %.1f%% | 최대 CPU: %.1f%% | 평균 NetworkIn: %.0f bytes", avg_cpu, max_cpu, avg_net_in_bytes)

    return {
        "avg_cpu": avg_cpu,
        "max_cpu": max_cpu,
        "avg_net_in_bytes": avg_net_in_bytes,
        "datapoints_count": len(cpu_avg_series),
    }


def get_current_instance_type(ec2, instance_id: str) -> str:
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    return resp["Reservations"][0]["Instances"][0]["InstanceType"]


# ──────────────────────────────────────────────
# 안전성 검증
# ──────────────────────────────────────────────

def evaluate_safety(avg_cpu: float, max_cpu: float, avg_net_in_bytes: float) -> dict:
    """
    다운사이즈 안전성 평가 기준:
    - avg_cpu < 20%: 다운사이즈 안전
    - max_cpu > 80%: 고부하 spike 존재 → 비권장
    - avg_net_in > 50MB/s: 네트워크 집약적 워크로드 → 유지 권장
    """
    risks: list[str] = []

    if max_cpu > 80:
        risks.append(f"CPU spike 감지: 최대 {max_cpu}% (임계치 80% 초과) — 다운사이즈 비권장")

    if avg_cpu > 50:
        risks.append(f"평균 CPU 높음: {avg_cpu}% — 현재 타입 유지 권장")

    if avg_net_in_bytes > 50 * 1024 * 1024:
        gb = round(avg_net_in_bytes / 1024 / 1024, 1)
        risks.append(f"네트워크 집약적 워크로드: 평균 {gb} MB/s")

    return {
        "safe_to_downsize": len(risks) == 0,
        "risks": risks,
    }


# ──────────────────────────────────────────────
# 최적화 옵션 생성
# ──────────────────────────────────────────────

def generate_options(current_type: str) -> list[dict]:
    """최소 3가지 최적화 옵션 생성."""
    spec = INSTANCE_PRICING.get(current_type)
    if not spec:
        log.warning("알 수 없는 인스턴스 타입: %s — t3.small 기준으로 계산", current_type)
        spec = INSTANCE_PRICING["t3.small"]

    current_monthly = spec["hourly_usd"] * MONTHLY_HOURS
    options = []

    # Option 1: t3.micro 다운사이즈
    micro = INSTANCE_PRICING["t3.micro"]
    micro_monthly = micro["hourly_usd"] * MONTHLY_HOURS
    options.append({
        "rank": 1,
        "option": "Downsize to t3.micro",
        "type": "t3.micro",
        "monthly_usd": round(micro_monthly, 2),
        "saving_usd": round(current_monthly - micro_monthly, 2),
        "saving_pct": round((1 - micro_monthly / current_monthly) * 100, 1),
        "risk_level": "Medium",
        "risk_detail": "메모리 1GB (현재 2GB 대비 50% 감소). 메모리 사용률 확인 필수.",
        "note": "평균 CPU < 20%, 메모리 여유 있을 때 권장. 자동매매 봇 수준에서는 대부분 충분.",
        "prerequisite": "CloudWatch Memory 메트릭 확인 (CloudWatch Agent 설치 필요)",
    })

    # Option 2: Spot Instance 전환
    spot_hourly = spec["hourly_usd"] * (1 - SPOT_DISCOUNT_RATE)
    spot_monthly = spot_hourly * MONTHLY_HOURS
    options.append({
        "rank": 2,
        "option": f"Spot Instance 전환 ({current_type})",
        "type": f"{current_type} (Spot)",
        "monthly_usd": round(spot_monthly, 2),
        "saving_usd": round(current_monthly - spot_monthly, 2),
        "saving_pct": round(SPOT_DISCOUNT_RATE * 100, 1),
        "risk_level": "High",
        "risk_detail": "AWS가 Spot 회수 시 2분 전 통지 후 인스턴스 중단. 자동매매 중단 위험.",
        "note": "비용 최우선 시나리오. systemd restart + Telegram alert와 병행 필수. 전략 비활성 기간에 적합.",
        "prerequisite": "Spot 중단 알림 스크립트 추가, 미완료 주문 롤백 로직 구현 필요",
    })

    # Option 3: AMI 스냅샷 후 인스턴스 중지 (비활성 기간)
    ebs_monthly = 0.8  # EBS gp3 30GB 기준 약 $0.8/월
    options.append({
        "rank": 3,
        "option": "비활성 기간 인스턴스 중지 (AMI Snapshot)",
        "type": "Stop + AMI Snapshot",
        "monthly_usd": round(ebs_monthly, 2),
        "saving_usd": round(current_monthly - ebs_monthly, 2),
        "saving_pct": round((1 - ebs_monthly / current_monthly) * 100, 1),
        "risk_level": "Low",
        "risk_detail": "재시작 시 Public IP 변경 → Binance API whitelist 업데이트 필요.",
        "note": "전략 비활성 기간(백테스트 전환, 전략 일시 중단)에 최적. Elastic IP 사용 시 IP 고정 가능.",
        "prerequisite": "Elastic IP 할당 또는 Binance whitelist 자동 업데이트 스크립트",
    })

    return options


# ──────────────────────────────────────────────
# 리포트 저장
# ──────────────────────────────────────────────

def save_json_report(report: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = REPORT_DIR / f"cost_report_{date_str}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("JSON 리포트 저장: %s", path)
    return path


def save_html_report(report: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = REPORT_DIR / f"cost_report_{date_str}.html"

    safety = report["safety"]
    safety_class = "safe" if safety["safe_to_downsize"] else "warn"
    safety_label = "✅ 다운사이즈 안전" if safety["safe_to_downsize"] else "⚠️ 주의 필요"

    risks_html = (
        "\n".join(f"<li>{r}</li>" for r in safety["risks"])
        if safety["risks"]
        else "<li>감지된 위험 없음</li>"
    )

    options_html = ""
    for opt in report["options"]:
        risk_class = {"Low": "safe", "Medium": "neutral", "High": "warn"}.get(opt["risk_level"], "")
        options_html += f"""
        <tr>
            <td><strong>{opt['rank']}. {opt['option']}</strong></td>
            <td><code>{opt['type']}</code></td>
            <td>${opt['monthly_usd']}/월</td>
            <td><strong>${opt['saving_usd']}</strong> ({opt['saving_pct']}%)</td>
            <td class="{risk_class}">{opt['risk_level']}</td>
            <td>{opt['risk_detail']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>EC2 비용 최적화 보고서 {date_str}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 1000px; margin: 2rem auto; padding: 1rem; color: #333; }}
  h1 {{ color: #232f3e; border-bottom: 3px solid #ff9900; padding-bottom: .5rem; }}
  h2 {{ color: #232f3e; margin-top: 2rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: .9rem; }}
  th {{ background: #232f3e; color: white; padding: 10px 8px; text-align: left; }}
  td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  .safe {{ color: #2e7d32; font-weight: bold; }}
  .warn {{ color: #e65100; font-weight: bold; }}
  .neutral {{ color: #1565c0; font-weight: bold; }}
  .notice {{ background: #fff3cd; border-left: 4px solid #ff9900;
             padding: 1rem; margin-top: 2rem; border-radius: 4px; }}
  code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-size: .85rem; }}
</style>
</head>
<body>
<h1>📊 EC2 비용 최적화 보고서</h1>
<p>
  생성일: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M')}</strong> &nbsp;|&nbsp;
  인스턴스: <code>{report['instance_id']}</code> &nbsp;|&nbsp;
  리전: <code>{report['region']}</code> &nbsp;|&nbsp;
  분석 기간: 지난 {report['lookback_days']}일
</p>

<h2>현재 상태</h2>
<table>
  <tr><th>항목</th><th>값</th></tr>
  <tr><td>인스턴스 타입</td><td><code>{report['current_type']}</code></td></tr>
  <tr><td>평균 CPU (30일)</td><td>{report['metrics']['avg_cpu']}%</td></tr>
  <tr><td>최대 CPU (30일)</td><td>{report['metrics']['max_cpu']}%</td></tr>
  <tr><td>평균 NetworkIn</td><td>{round(report['metrics']['avg_net_in_bytes'] / 1024, 1)} KB/s</td></tr>
  <tr><td>다운사이즈 안전성</td>
      <td class="{safety_class}">{safety_label}</td></tr>
</table>

<h2>감지된 위험 요소</h2>
<ul>{risks_html}</ul>

<h2>최적화 옵션 (3가지)</h2>
<table>
  <tr>
    <th>옵션</th><th>타입</th><th>예상 월 비용</th>
    <th>절감액</th><th>위험도</th><th>위험 상세</th>
  </tr>
  {options_html}
</table>

<div class="notice">
  <strong>⚠️ 주의</strong><br>
  이 보고서는 참고용 분석입니다. 실제 인스턴스 변경은 반드시 <strong>수동 검토 및 승인</strong> 후 진행하세요.
  자동매매 시스템의 특성상 인스턴스 타입 변경 전 반드시 백테스트 및 페이퍼 트레이딩으로 안정성을 확인하십시오.
</div>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
    log.info("HTML 리포트 저장: %s", path)
    return path


# ──────────────────────────────────────────────
# Slack 알림
# ──────────────────────────────────────────────

def send_slack_notification(report: dict, webhook_url: str) -> None:
    if not webhook_url:
        log.info("SLACK_WEBHOOK_URL 미설정 — Slack 전송 건너뜀")
        return

    safety = report["safety"]
    best = report["options"][0]
    status_emoji = "✅" if safety["safe_to_downsize"] else "⚠️"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 월간 EC2 비용 최적화 보고서"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*인스턴스*: `{report['instance_id']}`"},
                {"type": "mrkdwn", "text": f"*현재 타입*: `{report['current_type']}`"},
                {"type": "mrkdwn", "text": f"*평균 CPU (30일)*: `{report['metrics']['avg_cpu']}%`"},
                {"type": "mrkdwn", "text": f"*최대 CPU (30일)*: `{report['metrics']['max_cpu']}%`"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{status_emoji} *다운사이즈 안전성*: "
                    f"{'안전' if safety['safe_to_downsize'] else '주의 필요'}\n\n"
                    f"*최우선 추천*: {best['option']}\n"
                    f"절감 예상: *${best['saving_usd']}/월* ({best['saving_pct']}%) — 위험도: {best['risk_level']}\n\n"
                    f"_전체 3가지 옵션은 HTML 리포트를 확인하세요._"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "⚠️ 이 분석은 참고용입니다. 실제 변경은 수동 승인 후 진행하세요.",
                }
            ],
        },
    ]

    resp = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
    resp.raise_for_status()
    log.info("Slack 전송 완료 (HTTP %d)", resp.status_code)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> dict:
    if not INSTANCE_ID:
        raise ValueError(
            "EC2_INSTANCE_ID 환경변수가 설정되지 않았습니다.\n"
            "사용법: EC2_INSTANCE_ID=i-xxxxxxxxxxxxxxxxx python cost_optimizer.py"
        )

    log.info("=" * 60)
    log.info("EC2 비용 최적화 분석 시작")
    log.info("인스턴스: %s | 리전: %s | 분석 기간: 지난 %d일", INSTANCE_ID, REGION, LOOKBACK_DAYS)
    log.info("=" * 60)

    cw = boto3.client("cloudwatch", region_name=REGION)
    ec2 = boto3.client("ec2", region_name=REGION)

    # 1. CloudWatch 데이터 수집
    metrics = collect_metrics(cw, INSTANCE_ID)

    # 2. 현재 인스턴스 타입 확인
    log.info("현재 인스턴스 타입 확인 중...")
    current_type = get_current_instance_type(ec2, INSTANCE_ID)
    log.info("  현재 타입: %s", current_type)

    # 3. 안전성 검증
    log.info("안전성 검증 중...")
    safety = evaluate_safety(
        metrics["avg_cpu"], metrics["max_cpu"], metrics["avg_net_in_bytes"]
    )
    if safety["safe_to_downsize"]:
        log.info("  ✅ 다운사이즈 안전 — 위험 요소 없음")
    else:
        for risk in safety["risks"]:
            log.warning("  ⚠️  %s", risk)

    # 4. 최적화 옵션 생성
    log.info("최적화 옵션 생성 중...")
    options = generate_options(current_type)
    for opt in options:
        log.info(
            "  [옵션 %d] %s — $%.2f/월 절감 (%.1f%%) | 위험도: %s",
            opt["rank"], opt["option"], opt["saving_usd"], opt["saving_pct"], opt["risk_level"],
        )

    # 보고서 데이터 조립
    report = {
        "generated_at": datetime.now().isoformat(),
        "instance_id": INSTANCE_ID,
        "region": REGION,
        "lookback_days": LOOKBACK_DAYS,
        "current_type": current_type,
        "metrics": metrics,
        "safety": safety,
        "options": options,
    }

    # 5. 리포트 저장
    log.info("리포트 저장 중...")
    save_json_report(report)
    html_path = save_html_report(report)

    # 6. Slack 알림
    send_slack_notification(report, SLACK_WEBHOOK_URL)

    log.info("=" * 60)
    log.info("분석 완료")
    log.info("HTML 리포트: %s", html_path)
    log.info(
        "최우선 추천: %s ($%.2f/월 절감)",
        options[0]["option"], options[0]["saving_usd"],
    )
    log.info("")
    log.info("⚠️  실제 인스턴스 변경은 수동으로 승인 후 진행하세요.")
    log.info("=" * 60)

    return report


if __name__ == "__main__":
    main()

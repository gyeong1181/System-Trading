from __future__ import annotations

import json

import pandas as pd

from src.config import Settings


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _cagr_text(row: dict) -> str:
    cagr = row.get("cagr")
    if cagr is None:
        history_days = int(row.get("history_days", 0) or 0)
        total_return = float(row.get("backtest_metrics", {}).get("total_return_pct", 0.0))
        if history_days <= 0:
            return "-"
        years = history_days / 365.25
        if years <= 0 or (1.0 + total_return) <= 0:
            return "-"
        cagr = (1.0 + total_return) ** (1 / years) - 1
    return _pct(float(cagr))


def _reason_text(row: dict) -> str:
    reasons = row.get("decision_reasons_ko", [])
    if not reasons:
        return "핵심 기준 미충족"
    return ", ".join(reasons)


def _warning_text(row: dict) -> str:
    warnings = []
    if row.get("warning_low_trade_count"):
        warnings.append("거래 수 적음")
    if row.get("history_days", 0) < 1095:
        warnings.append("히스토리 부족")
    if not row.get("robustness", {}).get("pass", False):
        warnings.append("강건성 미통과")
    return ", ".join(warnings) if warnings else "-"


def _timeframe_scope_text(results: list[dict]) -> str:
    order = ["240", "360", "720", "D"]
    labels = {row["timeframe"]: row["timeframe_ko"] for row in results}
    ordered = [labels[key] for key in order if key in labels]
    remaining = [labels[key] for key in labels if key not in order]
    scope = ordered + remaining
    return "/".join(scope) if scope else "-"


def _build_summary_rows(results: list[dict]) -> list[dict]:
    rows = []
    for row in results:
        metrics = row["metrics"]
        backtest_metrics = row["backtest_metrics"]
        wfo = row["wfo_summary"]
        rows.append(
            {
                "순위": row["rank"],
                "전략": row["strategy_id"],
                "전략명": row["strategy_name_ko"],
                "심볼": row["symbol"],
                "시간프레임": row["timeframe_ko"],
                "최종판정": row["classification_ko"],
                "권장경로": row["recommended_mode_ko"],
                "백테스트수익률": _pct(backtest_metrics["total_return_pct"]),
                "백테스트CAGR": _cagr_text(row),
                "백테스트MDD": _pct(backtest_metrics["max_drawdown_pct"]),
                "백테스트PF": f"{backtest_metrics['profit_factor']:.2f}",
                "백테스트Sharpe": f"{backtest_metrics['sharpe']:.2f}",
                "양전월비율": _pct(row["positive_month_ratio"]),
                "WFO통과비율": _pct(wfo["pass_ratio"]),
                "WFO양전윈도비율": _pct(wfo["positive_ratio"]),
                "WFO중앙수익률": _pct(wfo["median_return_pct"]),
                "WFO중앙PF": f"{wfo['median_profit_factor']:.2f}",
                "WFO중앙MDD": _pct(wfo["median_max_drawdown_pct"]),
                "강건성": "통과" if row["robustness"]["pass"] else "미통과",
                "경고": _warning_text(row),
                "판정근거": _reason_text(row),
                "거래수": int(metrics["trade_count"]),
                "점수": f"{row['score']:.2f}",
            }
        )
    return rows


def write_research_reports(results: list[dict], settings: Settings) -> dict[str, str]:
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    html_path = settings.report_dir / "research_report.html"
    csv_path = settings.report_dir / "research_report.csv"
    json_path = settings.report_dir / "research_report.json"

    summary_rows = _build_summary_rows(results)
    timeframe_scope = _timeframe_scope_text(results)
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False, encoding="utf-8-sig")

    json_payload = {
        "summary_text_ko": f"ETHUSDT 중심 {timeframe_scope} 연구 결과입니다. S1을 우선 검증하고, S2는 보조 후보로만 유지했으며, S3는 기본 실행에서 제외했습니다.",
        "generated_for": "Bybit 개인 트레이딩 시스템",
        "results": results,
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison_rows = "".join(
        f"<tr><td>{row['전략']}</td><td>{row['시간프레임']}</td><td>{row['최종판정']}</td>"
        f"<td>{row['백테스트수익률']}</td><td>{row['백테스트CAGR']}</td><td>{row['백테스트MDD']}</td><td>{row['백테스트PF']}</td>"
        f"<td>{row['WFO통과비율']}</td><td>{row['WFO양전윈도비율']}</td><td>{row['강건성']}</td><td>{row['경고']}</td></tr>"
        for row in summary_rows
    )

    monthly_sections = []
    for result in results:
        rows = "".join(
            f"<tr><td>{item['month']}</td><td>{_pct(item['return_pct'])}</td></tr>"
            for item in result["monthly_returns"]
        )
        monthly_sections.append(
            f"<h3>{result['strategy_id']} / {result['timeframe_ko']} 월별 수익률</h3>"
            f"<table><thead><tr><th>월</th><th>수익률</th></tr></thead><tbody>{rows}</tbody></table>"
        )

    detail_sections = []
    for row in summary_rows:
        detail_sections.append(
            f"<h3>{row['전략']} {row['심볼']} {row['시간프레임']}</h3>"
            f"<p><strong>최종 판정:</strong> {row['최종판정']} / <strong>권장 경로:</strong> {row['권장경로']}</p>"
            f"<p><strong>판정 근거:</strong> {row['판정근거']}</p>"
            f"<p><strong>경고:</strong> {row['경고']}</p>"
        )

    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Bybit 연구 요약 리포트</title>
  <style>
    body {{ font-family: 'Malgun Gothic', sans-serif; margin: 32px; color: #15202b; }}
    h1, h2, h3 {{ color: #0f4c81; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #edf2f7; }}
    .note {{ color: #4a5568; margin-bottom: 18px; }}
  </style>
</head>
<body>
  <h1>Bybit 연구 요약 리포트</h1>
  <p class="note">현재 경로는 ETHUSDT 중심 {timeframe_scope} 비교에 집중합니다. S1을 우선 검증하고 S2는 보조 후보로만 유지하며 S3는 기본 실행에서 제외했습니다.</p>
  <h2>{timeframe_scope} 비교</h2>
  <table>
    <thead>
      <tr>
        <th>전략</th><th>시간프레임</th><th>최종판정</th><th>백테스트 수익률</th><th>백테스트 CAGR</th><th>백테스트 MDD</th>
        <th>백테스트 PF</th><th>WFO 통과 비율</th><th>WFO 양전 윈도 비율</th><th>강건성</th><th>경고</th>
      </tr>
    </thead>
    <tbody>{comparison_rows}</tbody>
  </table>
  <h2>판정 상세</h2>
  {''.join(detail_sections)}
  <h2>월별 수익률</h2>
  {''.join(monthly_sections)}
</body>
</html>"""
    html_path.write_text(html, encoding="utf-8")

    return {"html": str(html_path), "csv": str(csv_path), "json": str(json_path)}

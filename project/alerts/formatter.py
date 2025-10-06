"""Helpers to format alert messages for Telegram delivery."""
from __future__ import annotations

from typing import Iterable, List

from project.risk import RiskAdvisor
from project.signals.models import Signal


def _format_duplicate(signal: Signal) -> str:
    if signal.is_duplicate:
        return f"⚠️ 중복 신호 (동일 조건 {signal.signature_hits}회)"
    if signal.direction_hits > 1:
        return f"중복 {signal.direction_hits}회"
    return "없음"


def _format_categories(signal: Signal) -> List[str]:
    categories = signal.metadata.get("categories", {})
    sorted_items = sorted(categories.items(), key=lambda item: item[1]["value"], reverse=True)
    lines: List[str] = []
    for name, info in sorted_items[:3]:
        lines.append(
            f"  • {name}: {info['value']:.1f}점 (가중 {info['weight'] * 100:.0f}%)"
        )
    return lines


def _format_summary_line(signal: Signal) -> str:
    duplicate = _format_duplicate(signal)
    conditions = ", ".join(signal.conditions) or "조건 부족"
    return (
        f"• {signal.symbol} {signal.direction_label} {signal.score}점 ({signal.grade})"
        f" – {duplicate} – 조건: {conditions}"
    )


def _format_signal(signal: Signal, risk) -> str:
    duplicate_text = _format_duplicate(signal)
    conditions = ", ".join(signal.conditions) or "조건 부족"
    summary_items: List[str] = list(signal.metadata.get("summary", []))
    if not summary_items:
        summary_items.append("시스템 요약 데이터 부족")
    orderbook_bias = signal.metadata.get("orderbook_bias", "중립")
    lines = [
        f"📢 {signal.symbol} {signal.direction_label} 신호 ({signal.timeframe})",
        f"- 종합 점수: {signal.score}점 ({signal.grade})",
        f"- 충족 조건: {conditions}",
        f"- 파이어차트: {orderbook_bias}",
        f"- 최적 신호: {'✅' if signal.is_optimal else '❌'}",
        f"- 중복: {duplicate_text}",
        f"- 추천 레버리지: x{risk.leverage:g}",
        f"- 베팅금액: 계좌의 {risk.bet_pct:.1f}%",
        f"- 손익비: 1:{risk.risk_reward}",
        "- 근거 요약:",
    ]
    lines.extend(f"  • {item}" for item in summary_items[:5])
    category_lines = _format_categories(signal)
    if category_lines:
        lines.append("- 카테고리 점수:")
        lines.extend(category_lines)
    return "\n".join(lines)


def build_alert_message(signals: Iterable[Signal], risk_advisor: RiskAdvisor) -> str:
    timeframes: dict[str, List[Signal]] = {}
    for signal in signals:
        timeframes.setdefault(signal.timeframe, []).append(signal)

    sections: List[str] = []
    for timeframe, bucket in sorted(timeframes.items(), key=lambda item: item[0]):
        optimal = [signal for signal in bucket if signal.is_optimal]
        extras = [signal for signal in bucket if not signal.is_optimal]
        if not optimal and not extras:
            continue

        if optimal:
            for signal in optimal:
                risk = risk_advisor.recommend(signal)
                sections.append(_format_signal(signal, risk))
        elif extras:
            signal = extras[0]
            risk = risk_advisor.recommend(signal)
            sections.append(_format_signal(signal, risk))

        if extras:
            summary_lines = ["기타 신호 요약:"]
            summary_lines.extend(_format_summary_line(signal) for signal in extras)
            sections.append("\n".join(summary_lines))

    return "\n\n".join(section for section in sections if section)


__all__ = ["build_alert_message"]

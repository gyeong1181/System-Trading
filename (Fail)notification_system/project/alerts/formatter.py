"""Helpers to format alert messages for downstream delivery."""
from __future__ import annotations

from typing import Iterable, List

from project.signals.models import Signal

GRADE_LABELS = {
    "strong": "강력",
    "high": "우수",
    "opportunity": "기회",
    "observe": "관망",
}


def _get_trade_plan(signal: Signal) -> dict:
    return signal.metadata.get("trade_plan", {})


def _get_risk(signal: Signal) -> dict:
    return signal.metadata.get("risk_recommendation", {})


def _format_duplicate(signal: Signal) -> str:
    if signal.is_optimal:
        return "최적 신호"
    if signal.is_duplicate:
        return f"중복 {signal.signature_hits}회"
    if signal.direction_hits > 1:
        return f"동일 방향 {signal.direction_hits}회"
    return "신규"


def _top_category_notes(signal: Signal, limit: int = 3) -> List[str]:
    categories = signal.metadata.get("categories", {})
    ranked = sorted(categories.items(), key=lambda item: item[1]["value"], reverse=True)
    lines: List[str] = []
    for name, info in ranked[:limit]:
        value = info.get("value", 0.0)
        summary = (info.get("notes") or [""])[0]
        text = f"{name} {value:.1f}점"
        if summary:
            text = f"{text} {summary}"
        lines.append(text.strip())
    return lines


def _format_conditions(signal: Signal) -> str:
    conditions = signal.conditions
    if not conditions:
        return "조건 없음"
    return ", ".join(conditions[:5])


def _orderbook_label(raw_bias: str) -> str:
    mapping = {
        "bid-heavy": "매수 우위",
        "ask-heavy": "매도 우위",
        "balanced": "중립",
    }
    return mapping.get(raw_bias, raw_bias)


def _format_summary(signal: Signal) -> List[str]:
    summary_items = signal.metadata.get("summary", [])
    if not summary_items:
        return []
    return [f"- {item}" for item in summary_items[:5]]


def _format_leg_table(
    legs: List[dict],
    heading: str,
    *,
    show_disabled: bool = False,
) -> List[str]:
    if not legs:
        return []

    visible = [leg for leg in legs if show_disabled or leg.get("enabled", True)]
    if not visible:
        return []
    if len(visible) == 1 and abs(visible[0].get("size_pct", 1.0) - 1.0) < 1e-6:
        return []

    lines = [heading]
    for leg in legs:
        enabled = bool(leg.get("enabled", True))
        if not enabled and not show_disabled:
            continue
        price = leg.get("price")
        price_text = f"{price:.2f}" if isinstance(price, (int, float)) else str(price)
        status = leg.get("status", "pending")
        size_pct = leg.get("size_pct", 0.0) * 100
        label = leg.get("label", "")
        flag = "활성" if enabled else "비활성"
        lines.append(f"  - {label}: {price_text} | 비중 {size_pct:.1f}% | 상태 {status} ({flag})")
    return lines if len(lines) > 1 else []


def _format_signal(signal: Signal) -> str:
    plan = _get_trade_plan(signal)
    risk = _get_risk(signal)
    entry = plan.get("entry")
    target = plan.get("target")
    stop = plan.get("stop")
    leverage = risk.get("leverage")
    bet_pct = risk.get("bet_pct")
    risk_reward = risk.get("risk_reward")
    grade_label = GRADE_LABELS.get(signal.grade, signal.grade.title())
    delta = signal.metadata.get("score_delta")
    rolling = signal.metadata.get("score_rolling")

    trade_line = (
        f"📈 {signal.symbol} {signal.direction_label} 진입 {entry:.2f} → 목표 {target:.2f} / 손절 {stop:.2f}"
        if None not in (entry, target, stop)
        else f"📈 {signal.symbol} {signal.direction_label} 진입 계획 데이터 부족"
    )

    factor_notes = _top_category_notes(signal)
    reason_text = ", ".join(factor_notes) if factor_notes else ", ".join(signal.metadata.get("summary", []))

    header_line = f"🚀 신호등급: {grade_label}({signal.score}점) | 근거: {reason_text}"
    risk_line = (
        f"손익비 1:{risk_reward:.2f} / 레버리지 x{leverage:.2f} / 베팅 {bet_pct:.2f}%"
        if None not in (risk_reward, leverage, bet_pct)
        else "위험 매개변수 계산 불가"
    )
    condition_line = f"조건: {_format_conditions(signal)}"
    delta_text = f"{delta:.2f}" if isinstance(delta, (int, float)) else "N/A"
    rolling_text = f"{rolling:.2f}" if isinstance(rolling, (int, float)) else "N/A"
    duplicate_line = f"상태: {_format_duplicate(signal)} | Δ점수 {delta_text} / 롤링 {rolling_text}"
    orderbook = _orderbook_label(signal.metadata.get("orderbook_bias", "중립"))
    bias_line = f"체결/호가 편향: {orderbook}"

    entry_legs = plan.get("entry_legs", [])
    exit_legs = plan.get("exit_legs", [])
    entry_section: List[str] = []
    exit_section: List[str] = []

    if plan.get("partials_entry_enabled") and entry_legs:
        entry_section = _format_leg_table(entry_legs, "🧭 분할매수 계획", show_disabled=True)
    elif len(entry_legs) > 1:
        entry_section = _format_leg_table(entry_legs, "🧭 분할매수 계획", show_disabled=False)

    if plan.get("partials_exit_enabled") and exit_legs:
        exit_section = _format_leg_table(exit_legs, "🎯 분할매도 계획", show_disabled=False)
    elif len(exit_legs) > 1:
        exit_section = _format_leg_table(exit_legs, "🎯 분할매도 계획", show_disabled=False)

    details = _format_summary(signal)
    if not details and factor_notes:
        details = [f"- {note}" for note in factor_notes]
    body = "\n".join(details) if details else "- 추가 근거 데이터 없음"

    sections: List[str] = [
        trade_line,
        header_line,
        risk_line,
        condition_line,
        duplicate_line,
        bias_line,
    ]
    if entry_section:
        sections.extend(entry_section)
    if exit_section:
        sections.extend(exit_section)
    sections.append(body)
    return "\n".join(sections)


def build_alert_message(signals: Iterable[Signal]) -> str:
    timeframes: dict[str, List[Signal]] = {}
    for signal in signals:
        timeframes.setdefault(signal.timeframe, []).append(signal)

    sections: List[str] = []
    for timeframe, bucket in sorted(timeframes.items(), key=lambda item: item[0]):
        ordered = sorted(bucket, key=lambda sig: sig.score, reverse=True)
        section_lines = [f"[{timeframe}]"]
        section_lines.extend(_format_signal(signal) for signal in ordered[:1])
        if len(ordered) > 1:
            recap = "\n".join(
                f"- {sig.symbol} {sig.direction_label} {sig.score}점 Δ{sig.metadata.get('score_delta', 'N/A')}"
                for sig in ordered[1:3]
            )
            section_lines.append("보조 신호 요약:")
            section_lines.append(recap)
        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


__all__ = ["build_alert_message"]

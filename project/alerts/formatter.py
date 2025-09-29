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


def _format_summary_line(signal: Signal) -> str:
    duplicate = _format_duplicate(signal)
    return (
        f"• {signal.symbol} {signal.direction_label} {signal.score}점 ({signal.grade})"
        f" – {duplicate}"
    )


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
                duplicate_text = _format_duplicate(signal)
                lines = [
                    f"📢 {signal.symbol} {signal.direction_label} 신호 ({timeframe})",
                    f"- 점수: {signal.score} ({signal.grade})",
                    "- 최적 신호: ✅",
                    f"- 중복: {duplicate_text}",
                    f"- 레버리지: x{risk.leverage:g}",
                    f"- 베팅금액: 계좌의 {risk.bet_pct:.1f}%",
                    f"- 손익비: 1:{risk.risk_reward}",
                ]
                sections.append("\n".join(lines))
        elif extras:
            # No explicit optimal signal – fall back to first extra
            signal = extras[0]
            risk = risk_advisor.recommend(signal)
            duplicate_text = _format_duplicate(signal)
            lines = [
                f"📢 {signal.symbol} {signal.direction_label} 신호 ({timeframe})",
                f"- 점수: {signal.score} ({signal.grade})",
                "- 최적 신호: ❌",
                f"- 중복: {duplicate_text}",
                f"- 레버리지: x{risk.leverage:g}",
                f"- 베팅금액: 계좌의 {risk.bet_pct:.1f}%",
                f"- 손익비: 1:{risk.risk_reward}",
            ]
            sections.append("\n".join(lines))

        if extras:
            summary_lines = ["기타 신호 요약:"]
            summary_lines.extend(_format_summary_line(signal) for signal in extras)
            sections.append("\n".join(summary_lines))

    return "\n\n".join(section for section in sections if section)


__all__ = ["build_alert_message"]

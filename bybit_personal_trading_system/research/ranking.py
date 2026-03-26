from __future__ import annotations

from src.config import Settings


CLASSIFICATION_KO = {
    "candidate": "후보",
    "shadow": "섀도우",
    "reject": "제외",
}


TIMEFRAME_KO = {
    "240": "4시간",
    "360": "6시간",
    "720": "12시간",
    "D": "일봉",
}


def recommended_mode(result: dict, settings: Settings) -> str:
    if result["classification"] == "reject":
        return "중단"
    if result["demo_only"]:
        return "데모"
    if result["strategy_id"] in settings.mode["live_enabled_strategies"] and result["classification"] == "candidate":
        return "실거래 검토"
    return "데모 검증"


def rank_strategy_results(results: list[dict], settings: Settings) -> list[dict]:
    ranked = sorted(
        results,
        key=lambda item: (
            {"candidate": 0, "shadow": 1, "reject": 2}[item["classification"]],
            -item["score"],
            item["priority"],
            item["timeframe"],
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
        row["classification_ko"] = CLASSIFICATION_KO[row["classification"]]
        row["recommended_mode_ko"] = recommended_mode(row, settings)
        row["timeframe_ko"] = TIMEFRAME_KO.get(row["timeframe"], row["timeframe"])
    return ranked

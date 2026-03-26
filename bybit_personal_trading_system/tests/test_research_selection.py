from __future__ import annotations

from research.walk_forward import select_research_params


def test_select_research_params_prefers_higher_score_with_same_candidate_bucket() -> None:
    low_month_ratio = {
        "params": {"name": "higher_score"},
        "metrics": {
            "profit_factor": 2.19,
            "max_drawdown_pct": -0.0616,
            "total_return_pct": 0.3454,
        },
        "positive_month_ratio": 0.5306,
        "score": 61.11,
    }
    high_month_ratio = {
        "params": {"name": "higher_month_ratio"},
        "metrics": {
            "profit_factor": 1.85,
            "max_drawdown_pct": -0.0755,
            "total_return_pct": 0.3158,
        },
        "positive_month_ratio": 0.5918,
        "score": 53.44,
    }

    selected = select_research_params([high_month_ratio, low_month_ratio])
    assert selected["params"]["name"] == "higher_score"

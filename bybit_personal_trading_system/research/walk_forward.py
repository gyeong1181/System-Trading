from __future__ import annotations

from typing import Any

from research.backtest import run_backtest
from research.data_manager import interval_to_minutes
from src.config import Settings


def bars_for_days(timeframe: str, days: int) -> int:
    minutes = interval_to_minutes(timeframe)
    bars = int((days * 1440) / minutes)
    return max(bars, 1)


def window_lengths(settings: Settings, timeframe: str) -> tuple[int, int, int]:
    return (
        bars_for_days(timeframe, int(settings.research["in_sample_days"])),
        bars_for_days(timeframe, int(settings.research["out_sample_days"])),
        bars_for_days(timeframe, int(settings.research["step_days"])),
    )


def positive_month_ratio(monthly_returns: list[dict[str, Any]]) -> float:
    if not monthly_returns:
        return 0.0
    positives = sum(1 for item in monthly_returns if float(item["return_pct"]) > 0)
    return positives / len(monthly_returns)


def compute_cagr(total_return_pct: float, history_days: int) -> float:
    if history_days <= 0:
        return 0.0
    years = history_days / 365.25
    if years <= 0:
        return 0.0
    ending_value = 1.0 + total_return_pct
    if ending_value <= 0:
        return -1.0
    return (ending_value ** (1 / years)) - 1


def selection_score(metrics: dict[str, float], month_ratio: float) -> float:
    return (
        metrics["profit_factor"] * 14
        + metrics["total_return_pct"] * 70
        + month_ratio * 30
        - abs(metrics["max_drawdown_pct"]) * 180
        + metrics["sharpe"] * 3
    )


def analyze_full_grid(
    settings: Settings,
    strategy: object,
    symbol: str,
    frame,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    fee_rate = float(settings.execution["fee_rate"])
    slippage = float(settings.execution["slippage"])
    risk_pct = float(settings.risk["symbol_risk_pct"])
    full_results: list[dict[str, Any]] = []

    for params in strategy.param_grid():
        result = run_backtest(
            strategy=strategy,
            frame=frame,
            symbol=symbol,
            params=params,
            fee_rate=fee_rate,
            slippage=slippage,
            risk_pct=risk_pct,
            starting_equity=float(settings.starting_equity),
        )
        month_ratio = positive_month_ratio(result.monthly_returns)
        full_results.append(
            {
                "params": params,
                "metrics": result.metrics,
                "monthly_returns": result.monthly_returns,
                "score": selection_score(result.metrics, month_ratio),
                "positive_month_ratio": month_ratio,
            }
        )

    full_results.sort(key=lambda row: row["score"], reverse=True)
    selected = select_research_params(full_results)
    robustness = robustness_snapshot(full_results, selected["params"], settings)
    return full_results, selected, robustness


def select_research_params(full_results: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket(row: dict[str, Any]) -> tuple[int, float, float, float, float]:
        metrics = row["metrics"]
        month_ratio = row["positive_month_ratio"]
        candidate_like = int(
            metrics["profit_factor"] > 1.10
            and abs(metrics["max_drawdown_pct"]) < 0.10
            and month_ratio >= 0.50
            and metrics["total_return_pct"] > 0
        )
        shadow_like = int(
            metrics["profit_factor"] >= 1.00
            and abs(metrics["max_drawdown_pct"]) < 0.12
            and metrics["total_return_pct"] > 0
        )
        return (
            candidate_like,
            shadow_like,
            row["score"],
            metrics["total_return_pct"],
            metrics["profit_factor"],
            -abs(metrics["max_drawdown_pct"]),
        )

    ranked = sorted(full_results, key=bucket, reverse=True)
    return ranked[0]


def robustness_snapshot(
    full_results: list[dict[str, Any]],
    best_params: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    numeric_keys = [key for key, value in best_params.items() if isinstance(value, (int, float))]
    neighbors = []
    for row in full_results:
        if row["params"] == best_params:
            continue
        deviations = []
        for key in numeric_keys:
            best_value = float(best_params[key])
            compare_value = float(row["params"][key])
            if best_value == 0:
                deviations.append(0.0 if compare_value == 0 else 1.0)
            else:
                deviations.append(abs(compare_value - best_value) / abs(best_value))
        if deviations and (sum(deviations) / len(deviations)) <= 0.20:
            neighbors.append(row)

    plateau_ratio = float(settings.research["plateau_score_ratio"])
    plateau_neighbors = [row for row in neighbors if row["score"] >= full_results[0]["score"] * plateau_ratio]
    robustness_pass = False
    if plateau_neighbors:
        average_pf = sum(row["metrics"]["profit_factor"] for row in plateau_neighbors) / len(plateau_neighbors)
        average_return = sum(row["metrics"]["total_return_pct"] for row in plateau_neighbors) / len(plateau_neighbors)
        robustness_pass = average_pf >= 1.0 and average_return >= 0

    return {
        "pass": robustness_pass,
        "neighbor_count": len(neighbors),
        "plateau_count": len(plateau_neighbors),
    }


def summarize_wfo_windows(window_rows: list[dict[str, Any]]) -> dict[str, float]:
    if not window_rows:
        return {
            "window_count": 0.0,
            "pass_ratio": 0.0,
            "positive_ratio": 0.0,
            "median_return_pct": 0.0,
            "median_profit_factor": 0.0,
            "median_max_drawdown_pct": 0.0,
        }

    returns = sorted(float(row["metrics"]["total_return_pct"]) for row in window_rows)
    pfs = sorted(float(row["metrics"]["profit_factor"]) for row in window_rows)
    mdds = sorted(abs(float(row["metrics"]["max_drawdown_pct"])) for row in window_rows)

    def median(values: list[float]) -> float:
        mid = len(values) // 2
        if len(values) % 2 == 1:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    pass_count = sum(
        1
        for row in window_rows
        if row["metrics"]["profit_factor"] > 1.0
        and abs(row["metrics"]["max_drawdown_pct"]) < 0.10
        and row["metrics"]["total_return_pct"] > 0
    )
    positive_count = sum(1 for row in window_rows if row["metrics"]["total_return_pct"] > 0)
    count = len(window_rows)
    return {
        "window_count": float(count),
        "pass_ratio": pass_count / count,
        "positive_ratio": positive_count / count,
        "median_return_pct": median(returns),
        "median_profit_factor": median(pfs),
        "median_max_drawdown_pct": median(mdds),
    }


def classify_result(
    metrics: dict[str, float],
    monthly_returns: list[dict[str, Any]],
    robustness: dict[str, Any],
    wfo_summary: dict[str, float],
    settings: Settings,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    month_ratio = positive_month_ratio(monthly_returns)
    min_trades = int(settings.research["minimum_trade_count"])

    if metrics["profit_factor"] > 1.10:
        reasons.append("PF 1.10 초과")
    if abs(metrics["max_drawdown_pct"]) < 0.10:
        reasons.append("MDD 10% 미만")
    if month_ratio >= 0.50:
        reasons.append("양전 월 비율 50% 이상")
    if metrics["total_return_pct"] > 0:
        reasons.append("누적 수익 양수")
    if robustness["pass"]:
        reasons.append("플래토 강건성 통과")
    if wfo_summary["pass_ratio"] >= 0.50:
        reasons.append("WFO 통과 비율 50% 이상")

    if metrics["trade_count"] < min_trades:
        return "reject", reasons + ["거래 수가 너무 적음"]
    if (
        metrics["profit_factor"] > 1.10
        and abs(metrics["max_drawdown_pct"]) < 0.10
        and month_ratio >= 0.50
        and metrics["total_return_pct"] > 0
        and robustness["pass"]
        and wfo_summary["pass_ratio"] >= 0.50
    ):
        return "candidate", reasons
    if (
        metrics["profit_factor"] >= 1.00
        and abs(metrics["max_drawdown_pct"]) < 0.12
        and metrics["total_return_pct"] > 0
        and wfo_summary["positive_ratio"] >= 0.40
    ):
        return "shadow", reasons
    return "reject", reasons


def run_fixed_param_wfo(
    settings: Settings,
    strategy: object,
    symbol: str,
    timeframe: str,
    frame,
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    train_bars, test_bars, step_bars = window_lengths(settings, timeframe)
    fee_rate = float(settings.execution["fee_rate"])
    slippage = float(settings.execution["slippage"])
    risk_pct = float(settings.risk["symbol_risk_pct"])

    window_rows: list[dict[str, Any]] = []
    start = 0
    while start + train_bars + test_bars <= len(frame):
        test = frame.iloc[start + train_bars : start + train_bars + test_bars]
        result = run_backtest(
            strategy=strategy,
            frame=test,
            symbol=symbol,
            params=params,
            fee_rate=fee_rate,
            slippage=slippage,
            risk_pct=risk_pct,
            starting_equity=float(settings.starting_equity),
        )
        window_rows.append(
            {
                "window_start": str(test.index.min()) if not test.empty else "",
                "window_end": str(test.index.max()) if not test.empty else "",
                "params": params,
                "metrics": result.metrics,
            }
        )
        start += step_bars

    return window_rows, summarize_wfo_windows(window_rows)


def run_strategy_research(settings: Settings, strategy: object, symbol: str, timeframe: str, frame) -> dict[str, Any]:
    minimum_days = int(settings.research["minimum_history_days"])
    history_days = max(int((frame.index.max() - frame.index.min()).days), 0) if len(frame.index) else 0
    full_grid_results, selected, robustness = analyze_full_grid(settings, strategy, symbol, frame)
    window_rows, wfo_summary = run_fixed_param_wfo(
        settings=settings,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        frame=frame,
        params=selected["params"],
    )

    metrics = selected["metrics"]
    monthly_returns = selected["monthly_returns"]
    classification, reasons = classify_result(metrics, monthly_returns, robustness, wfo_summary, settings)
    low_trade_warning = metrics["trade_count"] < int(settings.research["warning_trade_count"])
    if history_days < minimum_days:
        reasons.append(f"히스토리가 {minimum_days}일 미만")
        if classification == "candidate":
            classification = "shadow"

    score = selection_score(metrics, selected["positive_month_ratio"]) + wfo_summary["pass_ratio"] * 12
    if robustness["pass"]:
        score += 5

    return {
        "strategy_id": strategy.strategy_id,
        "strategy_name_ko": strategy.display_name_ko,
        "symbol": symbol,
        "timeframe": timeframe,
        "classification": classification,
        "params": selected["params"],
        "score": score,
        "metrics": metrics,
        "backtest_metrics": metrics,
        "monthly_returns": monthly_returns,
        "windows": window_rows,
        "wfo_summary": wfo_summary,
        "demo_only": strategy.config.demo_only,
        "priority": strategy.config.priority,
        "positive_month_ratio": selected["positive_month_ratio"],
        "robustness": robustness,
        "history_days": history_days,
        "cagr": compute_cagr(metrics["total_return_pct"], history_days),
        "warning_low_trade_count": low_trade_warning,
        "decision_reasons_ko": reasons,
        "full_grid_top": full_grid_results[:5],
    }

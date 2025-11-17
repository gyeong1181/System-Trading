"""Performance analysis utilities for trading signal evaluation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

try:  # pragma: no cover - optional dependency
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - matplotlib optional
    plt = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


@dataclass
class AnalyzerResult:
    """Container for aggregated statistics and artifacts."""

    overview: Dict[str, float]
    by_strategy_path: Path
    json_summary_path: Path
    charts: Dict[str, Path]
    dashboard_path: Path


class PerformanceAnalyzer:
    """Compute and persist performance metrics for trading signals."""

    def __init__(
        self,
        *,
        database_path: Path,
        report_dir: Path,
        notifier,
        notify_summary: bool = True,
    ) -> None:
        self._database_path = database_path
        self._report_dir = report_dir
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._notifier = notifier
        self._notify_summary = notify_summary

    def run(self) -> Optional[AnalyzerResult]:
        df = self._load_signals()
        if df.empty:
            LOGGER.info("Performance analysis skipped (no signal records).")
            return None

        closed = self._prepare_closed_positions(df)
        if closed.empty:
            LOGGER.info("Performance analysis skipped (no closed positions yet).")
            return None

        summary = self._compute_summary(closed)
        ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        charts = self._build_charts(closed, ts_tag=ts_tag)
        csv_path, json_path = self._export_reports(summary, ts_tag=ts_tag)
        dashboard_path = self._export_dashboard(df=df, closed=closed, summary=summary, charts=charts, ts_tag=ts_tag)

        if self._notifier and self._notify_summary:
            self._notify(summary, charts)

        return AnalyzerResult(
            overview=summary["overview"],
            by_strategy_path=csv_path,
            json_summary_path=json_path,
            charts=charts,
            dashboard_path=dashboard_path,
        )

    def _load_signals(self) -> pd.DataFrame:
        conn = sqlite3.connect(self._database_path)
        try:
            df = pd.read_sql("SELECT * FROM v_signals_latest", conn)
        finally:
            conn.close()
        if df.empty:
            return df
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        df["symbol"] = df["symbol"].astype(str).str.upper()
        df["timeframe"] = df["timeframe"].astype(str)
        df["direction"] = df["direction"].astype(str).str.lower()
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        df["risk_reward"] = pd.to_numeric(df["risk_reward"], errors="coerce")
        df["pnl"] = pd.to_numeric(df.get("pnl"), errors="coerce")
        df["outcome"] = df.get("outcome", "open").fillna("open")
        return df

    def _prepare_closed_positions(self, df: pd.DataFrame) -> pd.DataFrame:
        closed = df[df["outcome"].isin(["target_hit", "stop_hit", "stale"])].copy()
        if closed.empty:
            return closed
        closed["win"] = closed["outcome"] == "target_hit"
        direction_sign = np.where(closed["direction"] == "long", 1.0, -1.0)

        entry_price = pd.to_numeric(closed["entry_price"], errors="coerce")
        pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
        closed["realized_pnl_pct"] = pnl * 100
        closed["realized_price"] = entry_price * (1 + (pnl * direction_sign))
        closed["timestamp"] = closed["created_at"]
        return closed

    def _compute_summary(self, closed: pd.DataFrame) -> Dict[str, object]:
        win_rate = float(closed["win"].mean() * 100)
        tp_rate = float((closed["outcome"] == "target_hit").mean() * 100)
        avg_pnl = float(closed["realized_pnl_pct"].mean())
        max_loss = float(closed["realized_pnl_pct"].min())
        max_gain = float(closed["realized_pnl_pct"].max())
        avg_score = float(closed["score"].mean())
        losses = closed[closed["realized_pnl_pct"] < 0]["realized_pnl_pct"]
        gains = closed[closed["realized_pnl_pct"] > 0]["realized_pnl_pct"]
        avg_rr = float(gains.mean() / abs(losses.mean())) if not gains.empty and not losses.empty else float("nan")
        corr = float(closed["score"].corr(closed["realized_pnl_pct"])) if closed["score"].notna().any() else float("nan")

        grouped = (
            closed.groupby(["symbol", "timeframe"])
            .agg(
                win_rate=("win", lambda s: float(s.mean() * 100)),
                avg_pnl=("realized_pnl_pct", lambda s: float(s.mean())),
                max_loss=("realized_pnl_pct", lambda s: float(s.min())),
                max_gain=("realized_pnl_pct", lambda s: float(s.max())),
                avg_score=("score", lambda s: float(s.mean())),
                rr=("realized_pnl_pct", lambda s: float(
                    s[s > 0].mean() / abs(s[s < 0].mean())
                ) if (s > 0).any() and (s < 0).any() else float("nan")),
                signal_count=("win", "count"),
            )
            .reset_index()
        )

        return {
            "overview": {
                "win_rate": win_rate,
                "take_profit_rate": tp_rate,
                "avg_pnl": avg_pnl,
                "max_loss": max_loss,
                "max_gain": max_gain,
                "avg_score": avg_score,
                "avg_rr": avg_rr,
                "score_corr": corr,
                "signal_count": int(len(closed)),
            },
            "by_strategy": grouped,
        }

    def _build_charts(self, closed: pd.DataFrame, *, ts_tag: str) -> Dict[str, Path]:
        charts: Dict[str, Path] = {}
        if plt is None or closed.empty:
            return charts

        scatter_path = self._report_dir / f"score_vs_pnl_{ts_tag}.png"
        plt.figure(figsize=(6, 4))
        plt.scatter(closed["score"], closed["realized_pnl_pct"], alpha=0.6)
        plt.xlabel("Score")
        plt.ylabel("Realized PnL (%)")
        plt.title("Score vs Realized PnL")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(scatter_path, dpi=180)
        plt.close()
        charts["score_scatter"] = scatter_path

        cumulative_path = self._report_dir / f"cumulative_pnl_{ts_tag}.png"
        ordered = closed.sort_values("timestamp")
        ordered["cumulative_pnl"] = ordered["realized_pnl_pct"].cumsum()
        plt.figure(figsize=(6, 4))
        plt.plot(ordered["timestamp"], ordered["cumulative_pnl"], color="royalblue")
        plt.xlabel("Time")
        plt.ylabel("Cumulative PnL (%)")
        plt.title("Cumulative PnL Over Time")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(cumulative_path, dpi=180)
        plt.close()
        charts["cumulative_pnl"] = cumulative_path

        winrate_path = self._report_dir / f"winrate_by_strategy_{ts_tag}.png"
        grouped = closed.groupby(["symbol", "timeframe"])["win"].mean().reset_index()
        labels = grouped.apply(lambda row: f"{row['symbol']} {row['timeframe']}", axis=1)
        plt.figure(figsize=(6, 4))
        plt.bar(labels, grouped["win"] * 100, color="seagreen")
        plt.ylabel("Win Rate (%)")
        plt.title("Win Rate by Strategy")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(winrate_path, dpi=180)
        plt.close()
        charts["winrate_bar"] = winrate_path

        return charts

    def _export_reports(self, summary: Dict[str, object], *, ts_tag: str) -> tuple[Path, Path]:
        csv_path = self._report_dir / f"performance_summary_{ts_tag}.csv"
        json_path = self._report_dir / f"performance_summary_{ts_tag}.json"

        summary["by_strategy"].to_csv(csv_path, index=False)
        payload = {
            "generated_at": ts_tag,
            "overview": summary["overview"],
            "by_strategy": summary["by_strategy"].to_dict(orient="records"),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return csv_path, json_path

    def _export_dashboard(
        self,
        *,
        df: pd.DataFrame,
        closed: pd.DataFrame,
        summary: Dict[str, object],
        charts: Dict[str, Path],
        ts_tag: str,
    ) -> Path:
        dashboard_dir = self._report_dir / "dashboards"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = dashboard_dir / f"performance_dashboard_{ts_tag}.md"

        total_signals = int(len(df))
        sent_signals = int((df.get("status") == "sent").sum()) if total_signals else 0
        filtered_signals = total_signals - sent_signals

        def _count_reason(reason_key: str) -> int:
            if "reasons" not in df.columns or df.empty:
                return 0
            return int(
                df["reasons"]
                .fillna("")
                .astype(str)
                .apply(
                    lambda raw: reason_key in {part.strip() for part in raw.split("|") if part.strip()}
                )
                .sum()
            )

        risk_blocks = _count_reason("risk_controller_block")
        atr_blocks = _count_reason("atr_spike")

        overview = summary.get("overview", {})

        def _format_table(headers: list[str], rows: list[list[str]]) -> str:
            header_line = "| " + " | ".join(headers) + " |"
            separator = "| " + " | ".join("---" for _ in headers) + " |"
            if not rows:
                return "\n".join([header_line, separator, "| (no data) |" + " |" * (len(headers) - 1)])
            body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
            return "\n".join([header_line, separator, body])

        metrics_rows = [
            ["Win rate", f"{overview.get('win_rate', float('nan')):.1f}%"],
            ["Take profit rate", f"{overview.get('take_profit_rate', float('nan')):.1f}%"],
            ["Average PnL", f"{overview.get('avg_pnl', float('nan')):.2f}%"],
            ["Average RR", f"{overview.get('avg_rr', float('nan')):.2f}"],
            ["Score/PnL correlation", f"{overview.get('score_corr', float('nan')):.2f}"],
            ["Signals analysed", str(overview.get("signal_count", 0))],
        ]

        def _format_signal_rows(frame: pd.DataFrame, *, top: bool) -> list[list[str]]:
            if frame.empty:
                return []
            ordered = frame.sort_values("realized_pnl_pct", ascending=not top).head(3)
            rows: list[list[str]] = []
            for _, row in ordered.iterrows():
                rows.append(
                    [
                        str(row.get("symbol", "")),
                        str(row.get("timeframe", "")),
                        f"{row.get('realized_pnl_pct', float('nan')):.2f}%",
                        str(row.get("outcome", "")),
                        row.get("timestamp", pd.NaT).isoformat() if not pd.isna(row.get("timestamp")) else "",
                    ]
                )
            return rows

        top_gain_rows = _format_signal_rows(closed, top=True)
        top_loss_rows = _format_signal_rows(closed, top=False)

        by_strategy = summary.get("by_strategy")
        strategy_rows: list[list[str]] = []
        if isinstance(by_strategy, pd.DataFrame) and not by_strategy.empty:
            ranked = by_strategy.sort_values("signal_count", ascending=False).head(8)
            for _, row in ranked.iterrows():
                label = f"{row['symbol']} {row['timeframe']}"
                strategy_rows.append(
                    [
                        label,
                        f"{row.get('win_rate', float('nan')):.1f}%",
                        f"{row.get('avg_pnl', float('nan')):.2f}%",
                        str(int(row.get("signal_count", 0))),
                    ]
                )

        chart_lines: list[str] = []
        for name, path in charts.items():
            try:
                rel_path = path.relative_to(self._report_dir)
            except ValueError:
                rel_path = path
            chart_lines.append(f"- {name.replace('_', ' ').title()}: `{rel_path.as_posix()}`")

        lines = [
            f"# Performance Dashboard ({ts_tag} UTC)",
            "",
            "## Highlights",
            f"- Total signals recorded: {total_signals}",
            f"- Signals dispatched: {sent_signals}",
            f"- Signals filtered: {filtered_signals}",
            f"- Risk controller blocks: {risk_blocks}",
            f"- ATR guard blocks: {atr_blocks}",
            "",
            "## Core Metrics",
            _format_table(["Metric", "Value"], metrics_rows),
            "",
        ]

        lines.extend(
            [
                "## Top Gainers",
                _format_table(["Symbol", "Timeframe", "PnL", "Outcome", "Timestamp"], top_gain_rows),
                "",
                "## Top Drawdowns",
                _format_table(["Symbol", "Timeframe", "PnL", "Outcome", "Timestamp"], top_loss_rows),
                "",
                "## Strategy Snapshot",
                _format_table(["Strategy", "Win Rate", "Avg PnL", "Signals"], strategy_rows),
                "",
            ]
        )

        if chart_lines:
            lines.extend(["## Charts", *chart_lines, ""])

        dashboard_path.write_text("\n".join(lines), encoding="utf-8")
        return dashboard_path

    def _notify(self, summary: Dict[str, object], charts: Dict[str, Path]) -> None:
        overview = summary["overview"]
        message_lines = [
            "📊 신호 성능 보고",
            f"- 승률: {overview['win_rate']:.1f}%",
            f"- 익절률: {overview['take_profit_rate']:.1f}%",
            f"- 평균 PnL: {overview['avg_pnl']:.2f}%",
            f"- 평균 RR: {overview['avg_rr']:.2f}",
            f"- 점수-수익 상관: {overview['score_corr']:.2f}",
            f"- 분석 신호 수: {overview['signal_count']}",
        ]
        attachments = list(charts.values())[:3]
        try:
            self._notifier.send_trade_alert("\n".join(message_lines), attachments=attachments)
        except Exception as exc:  # pragma: no cover - notification failure
            LOGGER.warning("Failed to send performance summary notification: %s", exc)


# Local import to avoid circular dependency
import sqlite3  # noqa: E402  # isort:skip

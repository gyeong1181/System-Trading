from __future__ import annotations

from datetime import UTC, datetime
import json

from alerts.telegram import TelegramNotifier
from execution.engine import ExecutionEngine
from portfolio.manager import PortfolioManager
from portfolio.risk import RiskManager
from research.data_manager import MarketDataManager
from research.ranking import rank_strategy_results
from research.reporting import write_research_reports
from research.walk_forward import run_strategy_research
from src.config import Settings, load_settings, require_trading_credentials
from src.db import Database
from src.paths import ensure_runtime_directories
from strategies import build_strategy_registry


class TradingService:
    def __init__(self, repo_root: str | None = None) -> None:
        self.settings: Settings = load_settings(repo_root)
        ensure_runtime_directories(self.settings.repo_root)
        self.db = Database(self.settings.database_path)
        self.db.initialize()
        self.data_manager = MarketDataManager(self.settings)
        self.notifier = TelegramNotifier(self.settings)

    def bootstrap(self) -> str:
        ensure_runtime_directories(self.settings.repo_root)
        self.db.initialize()
        if not (self.settings.repo_root / ".env").exists():
            self.db.log_event(
                "bootstrap_notice",
                ".env 파일이 없어 .env.example 기준으로 입력이 필요합니다.",
            )
            return "초기화가 끝났습니다. 다음으로 `.env` 파일을 입력한 뒤 `make research-all`을 실행하세요."
        self.db.log_event("bootstrap_complete", "시스템 초기화가 끝났습니다.")
        return "초기화가 끝났습니다. `make research-all` 또는 `make demo-start`를 실행할 수 있습니다."

    def data_fetch(self) -> str:
        strategies = build_strategy_registry(self.settings)
        summaries: list[str] = []
        seen: set[tuple[str, str]] = set()
        for strategy in strategies.values():
            for symbol in strategy.config.symbols:
                for timeframe in strategy.config.research_timeframes:
                    key = (symbol, timeframe)
                    if key in seen:
                        continue
                    seen.add(key)
                    bundle = self.data_manager.update_market_data(symbol, timeframe)
                    gap_count = bundle["validation"]["missing_bars"]
                    summaries.append(f"{symbol} {timeframe} 갱신 완료, 누락 바 {gap_count}개")
        self.db.log_event("data_fetch_complete", "시장 데이터 갱신이 끝났습니다.", payload={"summary": summaries})
        return "\n".join(summaries)

    def research_all(self) -> str:
        strategies = build_strategy_registry(self.settings)
        results = []
        for strategy in strategies.values():
            for symbol in strategy.config.symbols:
                for timeframe in strategy.config.research_timeframes:
                    dataset = self.data_manager.update_market_data(symbol, timeframe)
                    results.append(
                        run_strategy_research(
                            self.settings,
                            strategy,
                            symbol,
                            timeframe,
                            dataset["frame"],
                        )
                    )

        ranked = rank_strategy_results(results, self.settings)
        report_paths = write_research_reports(ranked, self.settings)
        self.settings.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.state_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "results": ranked,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.db.log_event(
            "research_complete",
            "리서치와 워크포워드 검증이 끝났습니다.",
            payload={"report_paths": report_paths, "count": len(ranked)},
        )
        top_lines = [
            f"{row['strategy_id']} {row['symbol']} {row['timeframe_ko']} -> {row['classification_ko']} / 점수 {row['score']:.2f}"
            for row in ranked[:6]
        ]
        return "리서치가 끝났습니다.\n" + "\n".join(top_lines)

    def report(self) -> str:
        if not self.settings.state_path.exists():
            return "리서치 결과가 없습니다. 먼저 `make research-all`을 실행하세요."
        state = json.loads(self.settings.state_path.read_text(encoding="utf-8"))
        report_paths = write_research_reports(state["results"], self.settings)
        self.db.log_event("report_complete", "리포트 파일을 다시 생성했습니다.", payload={"report_paths": report_paths})
        return "리포트 생성을 마쳤습니다.\n" + "\n".join(report_paths.values())

    def start(self, mode: str) -> str:
        if mode not in {"paper", "demo", "live"}:
            raise RuntimeError("지원하지 않는 실행 모드입니다.")
        if mode in {"demo", "live"}:
            require_trading_credentials(self.settings)
        strategies = build_strategy_registry(self.settings)
        risk_manager = RiskManager(self.settings, self.db)
        portfolio_manager = PortfolioManager(self.settings, self.db, risk_manager)
        engine = ExecutionEngine(
            settings=self.settings,
            db=self.db,
            notifier=self.notifier,
            data_manager=self.data_manager,
            portfolio_manager=portfolio_manager,
            strategies=strategies,
            mode=mode,
        )
        engine.run()
        return f"{mode} 모드 실행이 종료되었습니다."

    def _set_control(self, event_type: str, message: str) -> str:
        self.db.log_event(event_type, message)
        return message

    def pause(self) -> str:
        return self._set_control("system_pause", "시스템이 일시 중지되었습니다.")

    def resume(self) -> str:
        self.db.log_event("system_clear_kill", "킬 스위치가 해제되었습니다.")
        return self._set_control("system_resume", "시스템이 재개되었습니다.")

    def kill(self) -> str:
        return self._set_control("system_kill", "킬 스위치가 활성화되었습니다. 실행 중 엔진은 포지션 정리 후 종료합니다.")

    def status(self) -> str:
        state = self.db.get_control_state()
        positions = self.db.get_open_positions()
        latest_equity = self.db.get_latest_equity()
        recent_events = self.db.get_recent_events(limit=5)
        lines = [
            "시스템 상태",
            f"- 일시 중지: {'예' if state['paused'] else '아니오'}",
            f"- 킬 스위치: {'활성' if state['killed'] else '비활성'}",
            f"- 열린 포지션 수: {len(positions)}개",
        ]
        if latest_equity:
            lines.append(f"- 최근 총자산: {float(latest_equity['total_equity']):.2f} USDT")
        if self.settings.state_path.exists():
            lines.append(f"- 최신 리서치 상태 파일: {self.settings.state_path}")
        if recent_events:
            lines.append("- 최근 이벤트:")
            for event in reversed(recent_events):
                lines.append(f"  {event['timestamp']} | {event['message']}")
        return "\n".join(lines)

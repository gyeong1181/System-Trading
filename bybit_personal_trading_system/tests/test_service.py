from __future__ import annotations

from src.service import TradingService


def test_paper_start_does_not_require_trading_credentials(repo_root, monkeypatch) -> None:
    def fail_require_credentials(settings) -> None:  # pragma: no cover - defensive
        raise AssertionError("paper mode should not require trading credentials")

    class DummyEngine:
        def __init__(self, **kwargs) -> None:
            self.mode = kwargs["mode"]

        def run(self) -> None:
            return None

    monkeypatch.setattr("src.service.require_trading_credentials", fail_require_credentials)
    monkeypatch.setattr("src.service.ExecutionEngine", DummyEngine)

    service = TradingService(repo_root=str(repo_root))
    message = service.start("paper")

    assert "paper" in message.lower()

import os
import sys
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def build_client(tmp_db: Path):
    os.environ["TV_WEBHOOK_SECRET"] = "testsecret"
    os.environ["EXECUTION_MODE"] = "RECEIVE_ONLY"
    os.environ["TV_ALLOWED_SYMBOLS"] = "BTCUSDT"
    os.environ["TV_ALLOWED_TIMEFRAMES"] = "1h"
    os.environ["DB_PATH"] = str(tmp_db)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webhook_server as ws
    importlib.reload(ws)
    return TestClient(ws.app)


def test_secret_validation(tmp_path):
    client = build_client(tmp_path / "test.db")
    payload = {
        "secret": "wrong",
        "strategy_id": "s1",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "action": "OPEN",
        "side": "LONG",
        "signal_time": "now",
        "signal_id": "sig1",
    }
    resp = client.post("/tv/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected_secret"


def test_symbol_timeframe_validation(tmp_path):
    client = build_client(tmp_path / "test2.db")
    payload = {
        "secret": "testsecret",
        "strategy_id": "s1",
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "action": "OPEN",
        "side": "LONG",
        "signal_time": "now",
        "signal_id": "sig2",
    }
    resp = client.post("/tv/webhook", json=payload)
    assert resp.json()["status"] == "rejected_symbol"


def test_dedup(tmp_path):
    client = build_client(tmp_path / "test3.db")
    payload = {
        "secret": "testsecret",
        "strategy_id": "s1",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "action": "OPEN",
        "side": "LONG",
        "signal_time": "now",
        "signal_id": "sig3",
    }
    first = client.post("/tv/webhook", json=payload)
    assert first.json()["status"] in ("received_only", "duplicate")
    second = client.post("/tv/webhook", json=payload)
    assert second.json()["status"] == "duplicate"

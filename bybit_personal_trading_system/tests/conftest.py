from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    settings = (REPO_ROOT / "configs" / "settings.toml").read_text(encoding="utf-8")
    (root / "configs" / "settings.toml").write_text(settings, encoding="utf-8")
    (root / ".env").write_text(
        "BYBIT_API_KEY=test\nBYBIT_API_SECRET=test\nBYBIT_USE_TESTNET=true\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n",
        encoding="utf-8",
    )
    return root

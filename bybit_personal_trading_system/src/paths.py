from __future__ import annotations

from pathlib import Path


def discover_repo_root(explicit_root: str | None = None) -> Path:
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def ensure_runtime_directories(repo_root: Path) -> None:
    required = [
        repo_root / "data",
        repo_root / "data" / "market",
        repo_root / "data" / "runtime",
        repo_root / "logs",
        repo_root / "reports",
    ]
    for path in required:
        path.mkdir(parents=True, exist_ok=True)

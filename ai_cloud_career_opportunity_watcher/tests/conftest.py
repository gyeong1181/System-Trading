from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def app_settings(tmp_path):
    source_catalog_path = tmp_path / "sources.json"
    source_catalog_path.write_text(
        json.dumps(
            [
                {
                    "name": "테스트 채용 소스",
                    "source_type": "job",
                    "collector_kind": "greenhouse_jobs",
                    "url": "https://example.com/jobs",
                    "is_active": True,
                    "config": {
                        "board_token": "dummy",
                        "company_name": "테스트회사",
                        "location_keywords": ["seoul", "korea"],
                        "required_keywords": ["ai", "cloud"],
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "watcher.db"
    return Settings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        source_catalog_path=str(source_catalog_path),
        scheduler_enabled=False,
        collection_on_startup=False,
        telegram_bot_token="dummy-token",
        telegram_chat_id="dummy-chat",
    )


@pytest.fixture
def client(app_settings):
    with TestClient(create_app(app_settings)) as test_client:
        yield test_client


@pytest.fixture
def app(client):
    return client.app

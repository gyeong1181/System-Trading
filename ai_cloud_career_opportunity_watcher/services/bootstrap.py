from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings
from core.logger import configure_logging
from database.engine import DatabaseManager
from services.approval_service import ApprovalService
from services.collection_service import CollectionService
from services.digest_service import DigestService
from services.source_service import SourceService


def bootstrap_app(app: FastAPI, settings: Settings) -> None:
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.db = DatabaseManager(settings.database_url)
    app.state.db.create_tables()

    with app.state.db.session_scope() as session:
        source_service = SourceService(settings.source_catalog_path)
        source_service.sync_catalog(session)

    app.state.source_service = SourceService(settings.source_catalog_path)
    app.state.collection_service = CollectionService(settings)
    app.state.approval_service = ApprovalService()
    app.state.digest_service = DigestService(settings)

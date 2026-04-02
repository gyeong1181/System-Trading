from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from admin_ui.routes import router as admin_router
from app.config import Settings, get_settings
from scheduler.jobs import run_collection_cycle
from scheduler.runtime import start_scheduler
from services.bootstrap import bootstrap_app

BASE_DIR = Path(__file__).resolve().parents[1]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bootstrap_app(app, settings)
        scheduler = start_scheduler(app)
        app.state.scheduler = scheduler
        if settings.collection_on_startup:
            run_collection_cycle(app)
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=str(BASE_DIR / "admin_ui" / "static")), name="static")
    application.include_router(admin_router)

    @application.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/admin/")

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

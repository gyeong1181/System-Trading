from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.jobs import run_collection_cycle


def start_scheduler(app) -> BackgroundScheduler | None:
    settings = app.state.settings
    if not settings.scheduler_enabled:
        return None

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_collection_cycle,
        CronTrigger.from_crontab(settings.collection_cron),
        kwargs={"app": app},
        id="collection_cycle",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler

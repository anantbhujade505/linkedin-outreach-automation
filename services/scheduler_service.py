from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from models.schemas import Settings


class SchedulerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scheduler = AsyncIOScheduler(timezone=settings.yaml_config.app.timezone)

    def add_jobs(self, outreach_callable, followup_callable) -> None:
        self.scheduler.add_job(outreach_callable, CronTrigger.from_crontab(self.settings.yaml_config.scheduler.outreach_cron), id="outreach", replace_existing=True)
        self.scheduler.add_job(followup_callable, CronTrigger.from_crontab(self.settings.yaml_config.scheduler.followup_cron), id="followup", replace_existing=True)

    def start(self) -> None:
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=True)

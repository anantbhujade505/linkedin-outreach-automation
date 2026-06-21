from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from loguru import logger

from models.schemas import ProfileStatus, RunStatus, Settings
from repositories.sqlite_repository import SQLiteRepository
from services.browser_manager import BrowserManager
from services.linkedin_service import LinkedInService
from services.logging_service import configure_logging
from services.sheet_service import SheetService
from utils.timers import iso_now


class FollowupJob:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SQLiteRepository(settings.sqlite_path)
        self.sheet_service = SheetService(settings)
        self.linkedin = LinkedInService(settings)

    async def run(self) -> None:
        run_id = str(uuid.uuid4())
        self.repository.create_run(run_id, "followup")
        cutoff = (datetime.now(UTC) - timedelta(days=self.settings.yaml_config.scheduler.followup_after_days)).isoformat()
        followups = self.repository.pending_followups(cutoff)
        logger.info("Found {} pending followups older than cutoff", len(followups))
        try:
            async with BrowserManager(self.settings) as browser:
                page = await browser.new_page()
                await self.linkedin.ensure_logged_in(page)
                
                # Fetch all currently pending invitations in one go
                pending_urls = await self.linkedin.get_pending_invitations_from_manager(page)
                
                for followup in followups:
                    await self.process_followup(run_id, followup, pending_urls, page)
            self.repository.finish_run(run_id, RunStatus.SUCCESS)
        except Exception as exc:
            logger.exception("Followup run failed: {}", exc)
            self.repository.finish_run(run_id, RunStatus.FAILED, str(exc))
            raise

    async def process_followup(self, run_id: str, followup, pending_urls: list[str], page) -> None:
        try:
            profile_url = followup["linkedin_url"]
            from utils.validators import extract_linkedin_username
            target_username = extract_linkedin_username(profile_url)
            
            # Check if this profile is still in the pending manager list
            is_pending = False
            if target_username:
                is_pending = any(extract_linkedin_username(url) == target_username for url in pending_urls)
            
            if is_pending:
                # Still pending -> older than cutoff -> withdraw it
                withdrawn = await self.linkedin.withdraw_invitation_from_manager(page, profile_url)
                if withdrawn:
                    withdrawn_at = iso_now()
                    self.repository.mark_followup(followup["id"], "withdrawn", withdrawn_at=withdrawn_at)
                    self.repository.update_profile_status(followup["profile_id"], ProfileStatus.WITHDRAWN)
                    self.repository.record_action(run_id, "withdrawal", "success", followup["profile_id"])
                    if followup["sheet_row"]:
                        self.sheet_service.update_row(followup["sheet_row"], {"status": "withdrawn", "withdrawn_timestamp": withdrawn_at})
                else:
                    self.repository.record_action(run_id, "withdrawal", "skipped", followup["profile_id"])
            else:
                # No longer pending -> Check if they accepted
                accepted = await self.linkedin.detect_accepted(page, profile_url)
                if accepted:
                    accepted_at = iso_now()
                    self.repository.mark_followup(followup["id"], "accepted", accepted_at=accepted_at)
                    self.repository.update_profile_status(followup["profile_id"], ProfileStatus.ACCEPTED)
                    self.repository.record_action(run_id, "acceptance_detection", "success", followup["profile_id"])
                    if followup["sheet_row"]:
                        self.sheet_service.update_row(followup["sheet_row"], {"status": "accepted", "accepted_timestamp": accepted_at})
                else:
                    # They declined or it was withdrawn/expired
                    withdrawn_at = iso_now()
                    self.repository.mark_followup(followup["id"], "withdrawn", withdrawn_at=withdrawn_at)
                    self.repository.update_profile_status(followup["profile_id"], ProfileStatus.WITHDRAWN)
                    self.repository.record_action(run_id, "withdrawal", "automatic_cleanup", followup["profile_id"])
                    if followup["sheet_row"]:
                        self.sheet_service.update_row(followup["sheet_row"], {"status": "withdrawn", "withdrawn_timestamp": withdrawn_at, "error_message": "Request no longer pending and not accepted"})
        except Exception as exc:
            screenshot = await self.linkedin.capture_failure(page, run_id, followup["profile_id"])
            logger.exception("Followup failed: {} screenshot={}", followup["linkedin_url"], screenshot)
            self.repository.record_action(run_id, "followup", "failed", followup["profile_id"], {"error": str(exc), "screenshot": screenshot})
            if followup["sheet_row"]:
                self.sheet_service.update_row(followup["sheet_row"], {"error_message": f"{exc} | screenshot={screenshot}"})


async def main_async() -> None:
    settings = Settings.load()
    configure_logging(settings)
    await FollowupJob(settings).run()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

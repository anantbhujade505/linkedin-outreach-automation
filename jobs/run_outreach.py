from __future__ import annotations

import asyncio
import signal
import uuid

from loguru import logger

from agents.comment_generator import CommentGenerator
from agents.jitter_engine import HumanizationAgent
from agents.note_generator import NoteGenerator
from agents.note_reviewer import ReviewAgent
from models.schemas import ProfileStatus, RunStatus, Settings
from repositories.sqlite_repository import SQLiteRepository
from services.browser_manager import BrowserManager
from services.linkedin_service import LinkedInService
from services.llm_service import LLMService
from services.logging_service import configure_logging
from services.sheet_service import SheetService
from services.state_service import StateService
from utils.timers import iso_now, sleep_between


class OutreachJob:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = SQLiteRepository(settings.sqlite_path)
        self.sheet_service = SheetService(settings)
        self.state_service = StateService(settings, self.repository)
        self.llm_service = LLMService(settings)
        self.note_generator = NoteGenerator(self.llm_service)
        self.reviewer = ReviewAgent(self.llm_service)
        self.humanizer = HumanizationAgent()
        self.comment_generator = CommentGenerator(self.llm_service, settings.yaml_config.safety.emojis_allowed)
        self.linkedin = LinkedInService(settings)
        self.stop_requested = False

    async def run(self) -> None:
        run_id = str(uuid.uuid4())
        self.repository.create_run(run_id, "outreach")
        logger.info("Started outreach run {}", run_id)
        try:
            targets = self.sheet_service.read_targets(self.settings.yaml_config.safety.max_profiles_per_run)
            if not targets:
                logger.info("No eligible sheet targets found")
                self.repository.finish_run(run_id, RunStatus.SUCCESS)
                return
            async with BrowserManager(self.settings) as browser:
                page = await browser.new_page()
                await self.linkedin.ensure_logged_in(page)
                for target in targets:
                    if self.stop_requested:
                        self.repository.finish_run(run_id, RunStatus.STOPPED)
                        return
                    profile_id = self.repository.upsert_profile(
                        str(target.linkedin_url),
                        first_name=target.first_name,
                        company=target.company,
                        sheet_row=target.row_number,
                        status=ProfileStatus.IN_PROGRESS,
                    )
                    await self.process_target(run_id, profile_id, target, page)
                    await sleep_between(
                        self.settings.yaml_config.delays.between_profiles_seconds_min,
                        self.settings.yaml_config.delays.between_profiles_seconds_max,
                    )
            self.repository.finish_run(run_id, RunStatus.SUCCESS)
        except Exception as exc:
            logger.exception("Outreach run failed: {}", exc)
            self.repository.finish_run(run_id, RunStatus.FAILED, str(exc))
            raise

    async def process_target(self, run_id, profile_id, target, page) -> None:
        profile_url = str(target.linkedin_url)
        try:
            if not self.state_service.can_send_connection():
                self.repository.update_profile_status(profile_id, ProfileStatus.SKIPPED)
                self.sheet_service.update_row(target.row_number, {"status": "skipped", "error_message": "Daily connection limit reached"})
                return
            await self.linkedin.open_profile(page, profile_url)
            profile = await self.linkedin.extract_profile(page, profile_url)
            profile = await self.linkedin.open_activity_and_collect_posts(page, profile)
            self.repository.update_profile_context(profile_id, profile)

            liked_count = await self.linkedin.like_latest_posts(page, max_likes=3)
            self.repository.record_action(run_id, "like", "success", profile_id, {"count": liked_count})

            final_comment = None
            if profile.latest_posts and self.state_service.can_comment():
                draft_comment = await self.comment_generator.draft(profile, profile.latest_posts[0], self.settings.yaml_config.llm.comment_limit)
                final_comment = await self.reviewer.review_comment(draft_comment, profile, profile.latest_posts[0], self.settings.yaml_config.llm.comment_limit)
                posted = await self.linkedin.post_comment_on_latest(page, final_comment)
                self.repository.record_message(run_id, profile_id, "comment", draft_comment, final_comment, final_comment, self.settings.yaml_config.llm.comment_limit)
                self.repository.record_action(run_id, "comment", "success" if posted else "skipped", profile_id)

            note_limit = self.humanizer.choose_note_limit(
                self.settings.yaml_config.llm.note_option_a_limit,
                self.settings.yaml_config.llm.note_option_b_limit,
            )
            draft_note = await self.note_generator.draft(profile, target.notes, note_limit)
            reviewed_note = await self.reviewer.review_note(draft_note, profile, note_limit)
            final_note = self.humanizer.humanize(
                reviewed_note,
                note_limit,
                first_name=target.first_name,
                emojis_allowed=self.settings.yaml_config.safety.emojis_allowed,
            )
            self.repository.record_message(run_id, profile_id, "connection_note", draft_note, reviewed_note, final_note, note_limit)

            sent = await self.linkedin.send_connection_request(page, profile_url, final_note)
            status = ProfileStatus.REQUEST_SENT if sent else ProfileStatus.FAILED
            timestamp = iso_now() if sent else None
            self.repository.update_profile_status(profile_id, status)
            self.repository.record_action(run_id, "connection_request", "success" if sent else "failed", profile_id)
            if sent:
                self.repository.create_or_update_followup(profile_id, timestamp)
            self.sheet_service.update_row(
                target.row_number,
                {
                    "status": status.value,
                    "sent_timestamp": timestamp,
                    "generated_note": final_note,
                    "generated_comment": final_comment,
                    "error_message": "",
                },
            )
        except Exception as exc:
            screenshot = await self.linkedin.capture_failure(page, run_id, profile_id)
            logger.exception("Profile failed: {} screenshot={}", profile_url, screenshot)
            self.repository.update_profile_status(profile_id, ProfileStatus.FAILED)
            self.repository.record_action(run_id, "profile", "failed", profile_id, {"error": str(exc), "screenshot": screenshot})
            self.sheet_service.update_row(target.row_number, {"status": "failed", "error_message": f"{exc} | screenshot={screenshot}"})


async def main_async() -> None:
    settings = Settings.load()
    configure_logging(settings)
    job = OutreachJob(settings)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, setattr, job, "stop_requested", True)
    await job.run()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

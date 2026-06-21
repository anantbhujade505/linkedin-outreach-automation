from __future__ import annotations

from pathlib import Path
from typing import Iterable

from loguru import logger
from playwright.async_api import Page

from models.schemas import ExtractedProfile, Settings
from utils.selectors import first_text, first_visible
from utils.stealth import human_type, natural_click, random_mouse_movement, random_scroll
from utils.timers import iso_now, sleep_between
from utils.validators import clean_text, extract_linkedin_username


class LinkedInService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.selectors = settings.yaml_config.selectors

    async def ensure_logged_in(self, page: Page) -> None:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        if "login" not in page.url:
            return
        if self.settings.yaml_config.safety.require_manual_login:
            logger.warning("Manual LinkedIn login required. Complete login in the opened browser window.")
            await page.wait_for_url(lambda url: "linkedin.com/feed" in url, timeout=180000)
            return
        if not self.settings.linkedin_email or not self.settings.linkedin_password:
            raise ValueError("LinkedIn credentials are required when manual login is disabled")
        await page.fill("input[name='session_key']", self.settings.linkedin_email)
        await page.fill("input[name='session_password']", self.settings.linkedin_password)
        await page.click("button[type='submit']")
        await page.wait_for_url(lambda url: "linkedin.com/feed" in url, timeout=60000)

    async def open_profile(self, page: Page, profile_url: str) -> None:
        await page.goto(profile_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            logger.info("LinkedIn did not become network-idle; continuing after DOM load")
        await random_mouse_movement(page)
        await random_scroll(page)

    async def extract_profile(self, page: Page, profile_url: str) -> ExtractedProfile:
        name = await first_text(page, self.selectors.profile_name)
        headline = await first_text(page, self.selectors.headline)
        current_role = await first_text(page, self.selectors.current_role)
        mutual = await first_text(page, self.selectors.mutual_connections)
        recent_activity = None
        latest_posts: list[str] = []
        activity_link = await first_visible(page, self.selectors.activity_link)
        if activity_link:
            recent_activity = clean_text(await activity_link.inner_text())
        return ExtractedProfile(
            profile_url=profile_url,
            name=clean_text(name or ""),
            headline=clean_text(headline or ""),
            current_role=clean_text(current_role or ""),
            mutual_connections=clean_text(mutual or ""),
            recent_activity=recent_activity,
            latest_posts=latest_posts,
        )

    async def open_activity_and_collect_posts(self, page: Page, profile: ExtractedProfile, max_posts: int = 3) -> ExtractedProfile:
        activity_link = await first_visible(page, self.selectors.activity_link)
        if activity_link:
            await natural_click(activity_link)
            await page.wait_for_load_state("domcontentloaded")
        elif not page.url.endswith("/recent-activity/all/"):
            await page.goto(profile.profile_url.rstrip("/") + "/recent-activity/all/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await random_scroll(page)
        posts = []
        for selector in self.selectors.post_card:
            cards = page.locator(selector)
            count = min(await cards.count(), max_posts)
            for index in range(count):
                text = clean_text(await cards.nth(index).inner_text())
                if text and text not in posts:
                    posts.append(text[:2000])
            if posts:
                break
        profile.latest_posts = posts
        profile.recent_activity = posts[0][:500] if posts else profile.recent_activity
        return profile

    async def like_latest_posts(self, page: Page, max_likes: int = 3) -> int:
        if self.settings.dry_run:
            logger.info("DRY_RUN enabled; skipping real likes")
            return 0
        if not self.settings.yaml_config.safety.allow_liking:
            return 0
        liked = 0
        for selector in self.selectors.post_card:
            cards = page.locator(selector)
            count = min(await cards.count(), max_likes)
            for index in range(count):
                button = await first_visible(cards.nth(index), self.selectors.like_button, timeout=800)
                if button:
                    await natural_click(button)
                    liked += 1
                    await sleep_between(
                        self.settings.yaml_config.delays.within_profile_seconds_min,
                        self.settings.yaml_config.delays.within_profile_seconds_max,
                    )
            if liked:
                break
        return liked

    async def post_comment_on_latest(self, page: Page, comment: str) -> bool:
        if not self.settings.yaml_config.safety.allow_commenting:
            return False
        for selector in self.selectors.post_card:
            card = page.locator(selector).first
            if await card.count() == 0:
                continue
            button = await first_visible(card, self.selectors.comment_button, timeout=1000)
            if not button:
                continue
            await natural_click(button)
            editor = await first_visible(card, self.selectors.comment_editor, timeout=4000)
            if not editor:
                continue
            await human_type(
                editor,
                comment,
                self.settings.yaml_config.delays.typing_delay_ms_min,
                self.settings.yaml_config.delays.typing_delay_ms_max,
            )
            if self.settings.dry_run:
                logger.info("DRY_RUN enabled; comment typed but not posted")
                return True
            submit = await first_visible(card, self.selectors.comment_submit, timeout=3000)
            if submit:
                await natural_click(submit)
                return True
        return False

    async def send_connection_request(self, page: Page, profile_url: str, note: str) -> bool:
        await page.goto(profile_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            logger.info("LinkedIn did not become network-idle before connection flow; continuing")
        button = await first_visible(page, self.selectors.connect_button, timeout=3000)
        if not button:
            more = await first_visible(page, self.selectors.more_button, timeout=2000)
            if more:
                await natural_click(more)
                button = await first_visible(page, self.selectors.connect_button, timeout=3000)
        if not button:
            logger.warning("Connect button not found for {}", profile_url)
            return False
        await natural_click(button)
        add_note = await first_visible(page, self.selectors.add_note_button, timeout=4000)
        if add_note:
            await natural_click(add_note)
        textarea = await first_visible(page, self.selectors.note_textarea, timeout=4000)
        if textarea:
            await human_type(
                textarea,
                note,
                self.settings.yaml_config.delays.typing_delay_ms_min,
                self.settings.yaml_config.delays.typing_delay_ms_max,
            )
        if self.settings.dry_run:
            logger.info("DRY_RUN enabled; connection request prepared but not sent")
            return True
        send = await first_visible(page, self.selectors.send_button, timeout=4000)
        if send:
            await natural_click(send)
            return True
        return False

    async def detect_accepted(self, page: Page, profile_url: str) -> bool:
        await page.goto(profile_url, wait_until="domcontentloaded")
        text = clean_text(await page.locator("body").inner_text())
        return "Message" in text and "Pending" not in text and "Connect" not in text

    async def withdraw_pending_request(self, page: Page, profile_url: str) -> bool:
        if not self.settings.yaml_config.safety.allow_withdrawals:
            logger.warning("Withdrawals disabled by safety configuration")
            return False
        await page.goto(profile_url, wait_until="domcontentloaded")
        pending = await first_visible(page, ["button:has-text('Pending')", "span:has-text('Pending')"], timeout=4000)
        if not pending:
            return False
        if self.settings.dry_run:
            logger.info("DRY_RUN enabled; pending request detected but not withdrawn")
            return True
        await natural_click(pending)
        withdraw = await first_visible(page, ["button:has-text('Withdraw')"], timeout=4000)
        if withdraw:
            await natural_click(withdraw)
            confirm = await first_visible(page, ["button:has-text('Withdraw')"], timeout=4000)
            if confirm:
                await natural_click(confirm)
            return True
        return False

    async def get_pending_invitations_from_manager(self, page: Page) -> list[str]:
        url = self.selectors.sent_invitations_link
        logger.info("Checking Sent Invitations manager: {}", url)
        await page.goto(url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Scroll to load dynamically loaded items
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

        pending_urls: list[str] = []
        for selector in self.selectors.invitation_card:
            cards = page.locator(selector)
            card_count = await cards.count()
            if card_count > 0:
                for i in range(card_count):
                    card = cards.nth(i)
                    for link_sel in self.selectors.invitation_recipient_link:
                        link_loc = card.locator(link_sel)
                        link_count = await link_loc.count()
                        for j in range(link_count):
                            href = await link_loc.nth(j).get_attribute("href")
                            if href:
                                pending_urls.append(href)
                break
        logger.info("Found {} pending invitations in manager", len(pending_urls))
        return pending_urls

    async def withdraw_invitation_from_manager(self, page: Page, profile_url: str) -> bool:
        if not self.settings.yaml_config.safety.allow_withdrawals:
            logger.warning("Withdrawals disabled by safety configuration")
            return False

        target_username = extract_linkedin_username(profile_url)
        if not target_username:
            logger.warning("Could not extract username from profile URL: {}", profile_url)
            return False

        url = self.selectors.sent_invitations_link
        logger.info("Navigating to {} to withdraw pending request for {}", url, profile_url)
        await page.goto(url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

        for selector in self.selectors.invitation_card:
            cards = page.locator(selector)
            card_count = await cards.count()
            for i in range(card_count):
                card = cards.nth(i)
                found = False
                for link_sel in self.selectors.invitation_recipient_link:
                    link_loc = card.locator(link_sel)
                    link_count = await link_loc.count()
                    for j in range(link_count):
                        href = await link_loc.nth(j).get_attribute("href")
                        if href and extract_linkedin_username(href) == target_username:
                            found = True
                            break
                    if found:
                        break

                if found:
                    if self.settings.dry_run:
                        logger.info("DRY_RUN enabled; pending request for {} detected in manager but not withdrawn", profile_url)
                        return True

                    for btn_sel in self.selectors.invitation_withdraw_button:
                        btn = await first_visible(card, [btn_sel], timeout=2000)
                        if btn:
                            await natural_click(btn)
                            for confirm_sel in self.selectors.confirm_withdraw_button:
                                confirm_btn = await first_visible(page, [confirm_sel], timeout=3000)
                                if confirm_btn:
                                    await natural_click(confirm_btn)
                                    logger.info("Successfully withdrew invitation for {}", profile_url)
                                    return True
                            break
                    logger.warning("Found card for {} but failed to withdraw", profile_url)
                    return False

        logger.warning("Could not find pending invitation card for {}", profile_url)
        # Fallback to direct profile page withdrawal if possible
        logger.info("Attempting fallback direct profile withdrawal for {}", profile_url)
        return await self.withdraw_pending_request(page, profile_url)

    async def capture_failure(self, page: Page, run_id: str, profile_id: int | None = None) -> str:
        Path(self.settings.screenshot_dir).mkdir(parents=True, exist_ok=True)
        suffix = f"profile-{profile_id}" if profile_id else "unknown"
        path = Path(self.settings.screenshot_dir) / f"{run_id}-{suffix}-{iso_now().replace(':', '-')}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)

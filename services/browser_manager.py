from __future__ import annotations

import random
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from models.schemas import Settings
from utils.stealth import apply_stealth


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        cfg = self.settings.yaml_config.browser
        self.playwright = await async_playwright().start()
        Path(cfg.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(cfg.storage_state_path).parent.mkdir(parents=True, exist_ok=True)
        viewport = {
            "width": random.randint(cfg.viewport_width_min, cfg.viewport_width_max),
            "height": random.randint(cfg.viewport_height_min, cfg.viewport_height_max),
        }
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=cfg.user_data_dir,
            headless=cfg.headless,
            slow_mo=cfg.slow_mo_ms,
            viewport=viewport,
            locale="en-US",
            timezone_id=self.settings.yaml_config.app.timezone,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.context.set_default_navigation_timeout(cfg.navigation_timeout_ms)
        self.context.set_default_timeout(cfg.action_timeout_ms)
        await apply_stealth(self.context)

    async def new_page(self) -> Page:
        if self.context is None:
            await self.start()
        assert self.context is not None
        page = await self.context.new_page()
        return page

    async def save_state(self) -> None:
        if self.context:
            try:
                await self.context.storage_state(path=self.settings.yaml_config.browser.storage_state_path)
            except Exception as exc:
                logger.warning("Could not save browser storage state: {}", exc)

    async def close(self) -> None:
        if self.context:
            await self.save_state()
            try:
                await self.context.close()
            except Exception as exc:
                logger.warning("Could not close browser context cleanly: {}", exc)
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

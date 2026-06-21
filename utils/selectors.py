from __future__ import annotations

from playwright.async_api import Locator, Page


async def first_visible(page: Page | Locator, selectors: list[str], timeout: int = 1500) -> Locator | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception:
            continue
    return None


async def first_text(page: Page | Locator, selectors: list[str], timeout: int = 1000) -> str | None:
    locator = await first_visible(page, selectors, timeout=timeout)
    if not locator:
        return None
    try:
        return (await locator.inner_text()).strip()
    except Exception:
        return None

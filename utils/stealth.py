from __future__ import annotations

import random

from playwright.async_api import BrowserContext, Page


STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""


async def apply_stealth(context: BrowserContext) -> None:
    await context.add_init_script(STEALTH_INIT_SCRIPT)


async def random_mouse_movement(page: Page, moves: int | None = None) -> None:
    viewport = page.viewport_size or {"width": 1280, "height": 800}
    for _ in range(moves or random.randint(2, 5)):
        await page.mouse.move(
            random.randint(20, viewport["width"] - 20),
            random.randint(20, viewport["height"] - 20),
            steps=random.randint(5, 18),
        )


async def random_scroll(page: Page) -> None:
    for _ in range(random.randint(1, 4)):
        delta = random.randint(250, 900) * random.choice([1, 1, 1, -1])
        await page.mouse.wheel(0, delta)
        await page.wait_for_timeout(random.randint(350, 1400))


async def natural_click(locator) -> None:
    box = await locator.bounding_box()
    if box:
        page = locator.page
        await page.mouse.move(
            box["x"] + random.uniform(3, max(4, box["width"] - 3)),
            box["y"] + random.uniform(3, max(4, box["height"] - 3)),
            steps=random.randint(6, 16),
        )
        await page.wait_for_timeout(random.randint(120, 700))
    await locator.click(delay=random.randint(60, 240))


async def human_type(locator, text: str, min_delay_ms: int, max_delay_ms: int) -> None:
    await locator.fill("")
    for char in text:
        await locator.type(char, delay=random.randint(min_delay_ms, max_delay_ms))

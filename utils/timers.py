from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def random_int(min_value: int, max_value: int) -> int:
    if min_value > max_value:
        raise ValueError("minimum cannot be greater than maximum")
    return random.randint(min_value, max_value)


async def sleep_between(min_seconds: int, max_seconds: int) -> float:
    duration = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(duration)
    return duration

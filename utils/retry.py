from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

T = TypeVar("T")


def resilient(
    attempts: int = 3,
    initial: float = 1,
    maximum: float = 30,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(initial=initial, max=maximum),
        retry=retry_if_exception_type(retry_exceptions),
        reraise=True,
    )

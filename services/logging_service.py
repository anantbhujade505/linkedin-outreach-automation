from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from models.schemas import Settings


def configure_logging(settings: Settings) -> None:
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        colorize=True,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    )
    logger.add(
        Path(settings.log_dir) / "app.log",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        level=settings.log_level,
        enqueue=True,
        serialize=True,
        backtrace=False,
        diagnose=False,
    )


def get_logger():
    return logger

from __future__ import annotations

from pathlib import Path

import pytest

from models.schemas import Settings


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    settings = Settings.load()
    settings.sqlite_path = str(tmp_path / "outreach.sqlite3")
    settings.log_dir = str(tmp_path / "logs")
    settings.screenshot_dir = str(tmp_path / "screenshots")
    settings.dry_run = True
    settings.openrouter_api_key = "test-key"
    settings.google_sheet_id = "test-sheet"
    return settings

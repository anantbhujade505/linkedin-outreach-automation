from __future__ import annotations

from datetime import UTC, datetime, time

from models.schemas import Settings
from repositories.sqlite_repository import SQLiteRepository


class StateService:
    def __init__(self, settings: Settings, repository: SQLiteRepository) -> None:
        self.settings = settings
        self.repository = repository

    def can_send_connection(self) -> bool:
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC).isoformat()
        count = self.repository.count_actions_since("connection_request", today)
        return count < self.settings.yaml_config.safety.daily_connection_limit

    def can_comment(self) -> bool:
        today = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC).isoformat()
        count = self.repository.count_actions_since("comment", today)
        return count < self.settings.yaml_config.safety.daily_comment_limit

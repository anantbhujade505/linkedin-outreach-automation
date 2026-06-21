from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProfileStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CONNECTED = "connected"
    REQUEST_SENT = "request_sent"
    PENDING = "pending"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"
    SKIPPED = "skipped"
    FAILED = "failed"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"


class SheetTarget(BaseModel):
    row_number: int
    linkedin_url: HttpUrl
    first_name: str | None = None
    company: str | None = None
    notes: str | None = None
    status: str | None = None


class ExtractedProfile(BaseModel):
    profile_url: str
    name: str | None = None
    headline: str | None = None
    current_role: str | None = None
    mutual_connections: str | None = None
    recent_activity: str | None = None
    latest_posts: list[str] = Field(default_factory=list)


class GeneratedMessage(BaseModel):
    draft: str
    reviewed: str
    final: str
    char_limit: int

    @field_validator("final")
    @classmethod
    def no_blank_final(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("final message cannot be blank")
        return value


class OutreachResult(BaseModel):
    run_id: str
    profile_url: str
    status: ProfileStatus
    final_note: str | None = None
    comment: str | None = None
    sent_timestamp: datetime | None = None
    error_message: str | None = None


class AppConfig(BaseModel):
    name: str = "linkedin-outreach-automation"
    dry_run: bool = True
    timezone: str = "UTC"


class SafetyConfig(BaseModel):
    daily_connection_limit: int = 20
    daily_comment_limit: int = 25
    max_profiles_per_run: int = 10
    allow_commenting: bool = True
    allow_liking: bool = True
    allow_withdrawals: bool = False
    require_manual_login: bool = True
    emojis_allowed: bool = False


class BrowserConfig(BaseModel):
    headless: bool = False
    slow_mo_ms: int = 35
    storage_state_path: str = ".auth/linkedin-storage.json"
    user_data_dir: str = ".browser/linkedin"
    viewport_width_min: int = 1200
    viewport_width_max: int = 1500
    viewport_height_min: int = 780
    viewport_height_max: int = 980
    navigation_timeout_ms: int = 45000
    action_timeout_ms: int = 15000


class DelayConfig(BaseModel):
    between_profiles_seconds_min: int = 120
    between_profiles_seconds_max: int = 300
    within_profile_seconds_min: int = 2
    within_profile_seconds_max: int = 10
    typing_delay_ms_min: int = 50
    typing_delay_ms_max: int = 150
    idle_pause_seconds_min: int = 1
    idle_pause_seconds_max: int = 5


class LLMConfig(BaseModel):
    temperature: float = 0.35
    max_tokens: int = 500
    timeout_seconds: int = 45
    note_option_a_limit: int = 200
    note_option_b_limit: int = 300
    comment_limit: int = 500


class SchedulerConfig(BaseModel):
    outreach_cron: str = "0 9 * * MON-FRI"
    followup_cron: str = "0 10 * * *"
    followup_after_days: int = 14


class SelectorConfig(BaseModel):
    profile_name: list[str] = Field(default_factory=list)
    headline: list[str] = Field(default_factory=list)
    current_role: list[str] = Field(default_factory=list)
    mutual_connections: list[str] = Field(default_factory=list)
    connect_button: list[str] = Field(default_factory=list)
    more_button: list[str] = Field(default_factory=list)
    add_note_button: list[str] = Field(default_factory=list)
    note_textarea: list[str] = Field(default_factory=list)
    send_button: list[str] = Field(default_factory=list)
    activity_link: list[str] = Field(default_factory=list)
    post_card: list[str] = Field(default_factory=list)
    like_button: list[str] = Field(default_factory=list)
    comment_button: list[str] = Field(default_factory=list)
    comment_editor: list[str] = Field(default_factory=list)
    comment_submit: list[str] = Field(default_factory=list)
    sent_invitations_link: str = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"
    invitation_card: list[str] = Field(default_factory=list)
    invitation_recipient_link: list[str] = Field(default_factory=list)
    invitation_withdraw_button: list[str] = Field(default_factory=list)
    confirm_withdraw_button: list[str] = Field(default_factory=list)



class YAMLConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    delays: DelayConfig = Field(default_factory=DelayConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    selectors: SelectorConfig = Field(default_factory=SelectorConfig)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    dry_run: bool = True
    config_path: str = "config/config.yaml"

    linkedin_email: str | None = None
    linkedin_password: str | None = None

    google_sheet_id: str | None = None
    google_worksheet_name: str = "Targets"
    google_service_account_file: str = "secrets/google-service-account.json"
    local_targets_csv: str = "templates/linkedin_targets_template.csv"

    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    sqlite_path: str = "database/outreach.sqlite3"
    log_level: str = "INFO"
    log_dir: str = "logs"
    screenshot_dir: str = "screenshots"

    yaml_config: YAMLConfig = Field(default_factory=YAMLConfig)

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        config_file = Path(settings.config_path)
        if config_file.exists():
            raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            settings.yaml_config = YAMLConfig.model_validate(raw)
            settings.dry_run = settings.dry_run if "DRY_RUN" in os.environ else settings.yaml_config.app.dry_run
        return settings

    def require_llm_credentials(self) -> None:
        provider = self.llm_provider.lower()
        key_map = {
            "mock": "local",
            "openrouter": self.openrouter_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
        }
        if provider not in key_map:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        if not key_map[provider]:
            raise ValueError(f"Missing API key for LLM provider: {provider}")

    def require_sheet_credentials(self) -> None:
        if not self.google_sheet_id:
            raise ValueError("GOOGLE_SHEET_ID is required")
        if not Path(self.google_service_account_file).exists():
            raise ValueError(f"Google service account file not found: {self.google_service_account_file}")

    def as_safe_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        for key in list(data):
            if "key" in key or "password" in key:
                data[key] = "***" if data[key] else None
        return data

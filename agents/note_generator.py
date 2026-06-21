from __future__ import annotations

from models.schemas import ExtractedProfile
from services.llm_service import LLMService
from utils.validators import clean_text, enforce_limit


class NoteGenerator:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    async def draft(self, profile: ExtractedProfile, sheet_notes: str | None, char_limit: int) -> str:
        system = (
            "You write concise LinkedIn connection request notes. Use only provided context. "
            "Do not invent facts. Avoid sales language, hype, flattery, emojis, and calls to book meetings."
        )
        user = f"""
Write one connection request note under {char_limit} characters.

Profile context:
Name: {profile.name or ""}
Headline: {profile.headline or ""}
Current role: {profile.current_role or ""}
Mutual connections: {profile.mutual_connections or ""}
Recent activity: {profile.recent_activity or ""}
Sheet notes: {sheet_notes or ""}

Return only the note text.
"""
        return enforce_limit(clean_text(await self.llm.complete(system, user)), char_limit)

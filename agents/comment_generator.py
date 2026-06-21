from __future__ import annotations

from models.schemas import ExtractedProfile
from services.llm_service import LLMService
from utils.validators import clean_text, enforce_limit


class CommentGenerator:
    def __init__(self, llm: LLMService, emojis_allowed: bool = False) -> None:
        self.llm = llm
        self.emojis_allowed = emojis_allowed

    async def draft(self, profile: ExtractedProfile, post_text: str, char_limit: int) -> str:
        system = (
            "You write useful LinkedIn comments. Be specific to the post, professional, and concise. "
            "Avoid generic praise, self-promotion, sales language, and unsupported claims."
        )
        emoji_rule = "Emojis are allowed sparingly." if self.emojis_allowed else "Do not use emojis."
        user = f"""
Write one meaningful comment under {char_limit} characters.

{emoji_rule}

Profile:
Headline: {profile.headline or ""}
Current role: {profile.current_role or ""}

Post:
{post_text}

Return only the comment.
"""
        return enforce_limit(clean_text(await self.llm.complete(system, user)), char_limit)

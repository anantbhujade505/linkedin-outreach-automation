from __future__ import annotations

from models.schemas import ExtractedProfile
from services.llm_service import LLMService
from utils.validators import clean_text, enforce_limit, validate_message


class ReviewAgent:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    async def review_note(self, draft: str, profile: ExtractedProfile, char_limit: int) -> str:
        system = (
            "You are a strict reviewer for LinkedIn outreach notes. Fix issues while preserving factual accuracy. "
            "Reject hallucinations by removing unsupported claims. Keep the final text professional and specific."
        )
        user = f"""
Review and rewrite the note if needed.

Rules:
- Maximum {char_limit} characters.
- No sales pitch.
- No invented facts.
- Professional and personalized.
- Uses only this context: name={profile.name}, headline={profile.headline}, role={profile.current_role}, activity={profile.recent_activity}

Draft:
{draft}

Return only the final note.
"""
        reviewed = enforce_limit(clean_text(await self.llm.complete(system, user)), char_limit)
        errors = validate_message(
            reviewed,
            char_limit,
            [profile.name or "", profile.headline or "", profile.current_role or "", profile.recent_activity or ""],
            require_personalized=True,
        )
        if errors:
            fallback_name = (profile.name or "your work").split()[0]
            context = profile.current_role or profile.headline or "your recent LinkedIn activity"
            reviewed = enforce_limit(f"Hi {fallback_name}, I noticed {context}. I would be glad to connect and follow your work.", char_limit)
        return reviewed

    async def review_comment(self, draft: str, profile: ExtractedProfile, post_text: str, char_limit: int) -> str:
        system = "You review LinkedIn comments for professionalism, context, and factual accuracy."
        user = f"""
Rewrite this comment only if needed.

Rules:
- Maximum {char_limit} characters.
- No generic praise.
- No emojis.
- No sales language.
- Use only post/profile context.

Profile: {profile.name}, {profile.headline}, {profile.current_role}
Post: {post_text}
Draft: {draft}

Return only the reviewed comment.
"""
        reviewed = enforce_limit(clean_text(await self.llm.complete(system, user)), char_limit)
        errors = validate_message(reviewed, char_limit, [post_text, profile.headline or "", profile.current_role or ""], require_personalized=False)
        if errors:
            reviewed = enforce_limit("This is a thoughtful point, especially the practical angle you raised. Thanks for sharing the perspective.", char_limit)
        return reviewed

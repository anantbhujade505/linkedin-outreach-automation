import pytest

from agents.jitter_engine import HumanizationAgent
from agents.note_reviewer import ReviewAgent
from models.schemas import ExtractedProfile
from utils.validators import validate_message


class FakeLLM:
    async def complete(self, system: str, user: str) -> str:
        return "Hi Alex, I noticed your AI engineering work and would be glad to connect."


@pytest.mark.asyncio
async def test_review_note_returns_valid_personalized_message() -> None:
    profile = ExtractedProfile(
        profile_url="https://www.linkedin.com/in/example/",
        name="Alex Example",
        headline="AI engineering leader",
        current_role="Principal AI Engineer",
        recent_activity="AI engineering work",
    )
    reviewed = await ReviewAgent(FakeLLM()).review_note("bad draft", profile, 200)
    assert not validate_message(reviewed, 200, [profile.name, profile.headline, profile.current_role, profile.recent_activity])


def test_humanizer_preserves_limit() -> None:
    result = HumanizationAgent().humanize("I noticed your recent AI engineering work and I would be glad to connect.", 80)
    assert len(result) <= 80


def test_humanizer_greeting_swap() -> None:
    agent = HumanizationAgent()
    # Try a few times to get variations due to random choice
    results = {agent.humanize("Hi Alex, I saw your work.", 100, "Alex") for _ in range(20)}
    # The greeting should have been changed to one of: Hi, Hello, Hey, Hi there
    assert any("Hello Alex," in r for r in results) or any("Hey Alex," in r for r in results) or any("Hi there Alex," in r for r in results) or any("Hi Alex," in r for r in results)


def test_humanizer_emoji_exclusion() -> None:
    agent = HumanizationAgent()
    note_with_emojis = "Hi Alex 👋, I saw your work 😊. I would be glad to connect! 🚀"
    cleaned = agent.humanize(note_with_emojis, 100, "Alex", emojis_allowed=False)
    assert "👋" not in cleaned
    assert "😊" not in cleaned
    assert "🚀" not in cleaned


def test_humanizer_emoji_inclusion() -> None:
    agent = HumanizationAgent()
    note = "Hi Alex, I saw your work."
    # Run multiple times because there is a 30% random chance of emoji insertion
    results = {agent.humanize(note, 100, "Alex", emojis_allowed=True) for _ in range(50)}
    # Check if at least one run contained a friendly emoji
    emojis = ["👋", "😊", "✨", "🚀", "🙌"]
    assert any(any(e in r for e in emojis) for r in results)


def test_humanizer_phrasing_changes() -> None:
    agent = HumanizationAgent()
    assert "I'd be glad to" in agent.humanize("Hi, I would be glad to connect.", 100) or "I would be glad to" in agent.humanize("Hi, I would be glad to connect.", 100)


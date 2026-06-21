from __future__ import annotations

import re
from urllib.parse import urlparse

SPAM_TERMS = {
    "guaranteed",
    "limited time",
    "buy now",
    "free trial",
    "10x",
    "synergy",
    "sales call",
    "book a demo",
    "revolutionize",
}

SALES_PATTERNS = [
    re.compile(r"\b(schedule|book|hop on)\b.{0,20}\b(call|demo|meeting)\b", re.I),
    re.compile(r"\bmy company\b|\bour product\b|\bour solution\b", re.I),
]


def is_linkedin_profile_url(url: str) -> bool:
    parsed = urlparse(str(url))
    return parsed.scheme in {"http", "https"} and parsed.netloc.endswith("linkedin.com") and "/in/" in parsed.path


def extract_linkedin_username(url: str) -> str | None:
    match = re.search(r"/in/([^/\s\?]+)", url)
    return match.group(1).lower() if match else None



def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def validate_message(
    message: str,
    char_limit: int,
    allowed_context: list[str],
    require_personalized: bool = True,
) -> list[str]:
    errors: list[str] = []
    normalized = clean_text(message)
    if len(normalized) > char_limit:
        errors.append(f"Message exceeds {char_limit} characters")
    if len(normalized) < 20:
        errors.append("Message is too short to be useful")
    lowered = normalized.lower()
    for term in SPAM_TERMS:
        if term in lowered:
            errors.append(f"Spam/sales language detected: {term}")
    for pattern in SALES_PATTERNS:
        if pattern.search(normalized):
            errors.append("Sales-oriented phrasing detected")
    context_tokens = [clean_text(c).lower() for c in allowed_context if clean_text(c)]
    if require_personalized and context_tokens:
        if not any(token[:24] in lowered for token in context_tokens if len(token) >= 3):
            errors.append("Message does not appear to use extracted profile context")
    return errors


def enforce_limit(text: str, limit: int) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rstrip(" ,.;:")
    return trimmed + "."

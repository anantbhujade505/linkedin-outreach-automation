from __future__ import annotations

import random
import re

from utils.validators import clean_text, enforce_limit


class HumanizationAgent:
    def humanize(self, text: str, char_limit: int, first_name: str | None = None, emojis_allowed: bool = False) -> str:
        # 1. Alternate greeting styles
        greetings = ["Hi", "Hello", "Hey", "Hi there"]
        pattern = r"^(Hi|Hello|Hey|Hi there)\b\s*([^,\n]*),"
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            name_part = match.group(2).strip()
            new_greeting = random.choice(greetings)
            greeting_str = f"{new_greeting} {name_part}" if name_part else new_greeting
            text = f"{greeting_str}," + text[match.end():]

        # 2. Emoji inclusion / exclusion
        emojis = ["👋", "😊", "✨", "🚀", "🙌"]
        if emojis_allowed:
            # 30% chance to insert an emoji at the greeting or at the end
            if random.random() < 0.3:
                if "," in text:
                    parts = text.split(",", 1)
                    text = f"{parts[0]} {random.choice(emojis)},{parts[1]}"
                else:
                    text = text.rstrip(".") + f" {random.choice(emojis)}."
        else:
            # Strip emojis
            emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]+", flags=re.UNICODE)
            text = emoji_pattern.sub(r"", text)

        # 3. Phrasing variations
        variants = [
            lambda s: s,
            lambda s: s.replace("I would be glad to", "I'd be glad to"),
            lambda s: s.replace("I noticed", "I saw"),
            lambda s: s.replace("connect and follow", "connect and keep up with"),
            lambda s: s.replace("great to connect", "wonderful to connect"),
            lambda s: s.replace("hope to connect", "would love to connect"),
            lambda s: s.replace("I would love to connect", "I'd love to connect"),
            lambda s: s.replace("to learn more about", "to hear more about"),
        ]
        output = clean_text(random.choice(variants)(text))
        output = re.sub(r"!+", ".", output)
        output = output.replace("  ", " ")
        return enforce_limit(output, char_limit)

    def choose_note_limit(self, option_a: int, option_b: int) -> int:
        return random.choice([option_a, option_b])


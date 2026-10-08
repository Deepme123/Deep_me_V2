from pathlib import Path
import logging
from functools import lru_cache

from app.core.resource_files import resolve_resource_path

GREETING_PATH = resolve_resource_path("backend", "greeting_messages.txt")

FALLBACK_GREETING_MESSAGES = [
    "안녕! 오늘 기분은 어때? 🌿",
]


def _load_greeting_messages(path: Path) -> list[str]:
    try:
        txt = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logging.warning("[GreetingLoader] greeting_messages.txt not found. Using fallback.")
        return FALLBACK_GREETING_MESSAGES
    messages = [block.strip() for block in txt.split("---")]
    messages = [m for m in messages if m]
    return messages or FALLBACK_GREETING_MESSAGES


@lru_cache(maxsize=1)
def get_greeting_messages() -> list[str]:
    return _load_greeting_messages(GREETING_PATH)

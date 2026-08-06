from pathlib import Path
import logging
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent.parent
_CWD_BASE_DIR = Path.cwd() / "app" / "backend"
_DEFAULT_GREETING_PATH = BASE_DIR / "resources" / "greeting_messages.txt"
_CWD_GREETING_PATH = _CWD_BASE_DIR / "resources" / "greeting_messages.txt"
GREETING_PATH = _DEFAULT_GREETING_PATH if _DEFAULT_GREETING_PATH.exists() else _CWD_GREETING_PATH

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

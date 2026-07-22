from pathlib import Path
import logging
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent
_CWD_BASE_DIR = Path.cwd() / "app" / "analyze"

_DEFAULT_CARD_PROMPT_PATH = BASE_DIR / "resources" / "card_system_prompt.txt"
_CWD_CARD_PROMPT_PATH = _CWD_BASE_DIR / "resources" / "card_system_prompt.txt"
CARD_PROMPT_PATH = (
    _DEFAULT_CARD_PROMPT_PATH if _DEFAULT_CARD_PROMPT_PATH.exists() else _CWD_CARD_PROMPT_PATH
)

FALLBACK_CARD_PROMPT_TEMPLATE = (
    "You are a warm, empathetic counselor who reads a counseling conversation and "
    "extracts a structured emotion card. Return JSON only, in Korean.\n\n{taxonomy_block}"
)


@lru_cache(maxsize=1)
def _load_card_prompt_template() -> str:
    try:
        return CARD_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logging.warning("[PromptLoader] card_system_prompt.txt not found. Using fallback.")
        return FALLBACK_CARD_PROMPT_TEMPLATE


def get_card_system_prompt(taxonomy_block: str) -> str:
    return _load_card_prompt_template().format(taxonomy_block=taxonomy_block)

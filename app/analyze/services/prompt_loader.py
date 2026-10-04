from functools import lru_cache

from app.core.resource_files import read_prompt, resolve_resource_path

CARD_PROMPT_PATH = resolve_resource_path("analyze", "card_system_prompt.txt")

FALLBACK_CARD_PROMPT_TEMPLATE = (
    "You are a warm, empathetic counselor who reads a counseling conversation and "
    "extracts a structured emotion card. Return JSON only, in Korean.\n\n{taxonomy_block}"
)


@lru_cache(maxsize=1)
def _load_card_prompt_template() -> str:
    return read_prompt(CARD_PROMPT_PATH, FALLBACK_CARD_PROMPT_TEMPLATE)


def get_card_system_prompt(taxonomy_block: str) -> str:
    return _load_card_prompt_template().format(taxonomy_block=taxonomy_block)

from __future__ import annotations

from functools import lru_cache

from app.core.llm import LLMProvider, create_llm_provider
from app.desire.core.config import settings


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return create_llm_provider(
        model_default=settings.openai_model,
        model_legacy_names=("NEED_CARD_MODEL",),
        temperature_default=settings.llm_temperature,
        max_tokens_default=settings.llm_max_tokens,
        timeout_default=settings.llm_timeout_sec,
    )

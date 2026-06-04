from __future__ import annotations

from functools import lru_cache

from app.core.llm import LLMProvider, create_llm_provider


@lru_cache(maxsize=1)
def get_backend_provider() -> LLMProvider:
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        timeout_default=60.0,
    )


@lru_cache(maxsize=1)
def get_card_provider() -> LLMProvider:
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        max_tokens_default=1500,
        timeout_default=60.0,
    )


@lru_cache(maxsize=1)
def get_task_provider() -> LLMProvider:
    return create_llm_provider(
        model_default="gpt-3.5-turbo",
        max_tokens_default=800,
    )


@lru_cache(maxsize=1)
def get_desire_provider() -> LLMProvider:
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        model_legacy_names=("NEED_CARD_MODEL",),
        timeout_default=15.0,
    )

from __future__ import annotations

from typing import Sequence

from app.core.llm_settings import LLMSettings, get_llm_settings

from .base import LLMProvider
from .openai_provider import OpenAIProvider


def create_llm_provider(
    *,
    model_default: str,
    model_legacy_names: Sequence[str] = (),
    temperature_default: float = 0.7,
    max_tokens_default: int = 800,
    timeout_default: float = 60.0,
) -> LLMProvider:
    settings = get_llm_settings(
        model_default=model_default,
        model_legacy_names=model_legacy_names,
        temperature_default=temperature_default,
        max_tokens_default=max_tokens_default,
        timeout_default=timeout_default,
    )
    return create_llm_provider_from_settings(settings)


def create_llm_provider_from_settings(settings: LLMSettings) -> LLMProvider:
    provider = settings.provider.strip().lower()
    if provider == "openai":
        return OpenAIProvider(settings=settings)
    raise ValueError(f"Unsupported LLM provider: {settings.provider}")

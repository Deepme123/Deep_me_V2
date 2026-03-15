from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .types import JSONValue, LLMJsonSchema, LLMMessage, LLMRequestOptions


def create_llm_provider(
    *,
    model_default: str,
    model_legacy_names=(),
    temperature_default: float = 0.7,
    max_tokens_default: int = 800,
    timeout_default: float = 60.0,
) -> LLMProvider:
    from .factory import create_llm_provider as _create_llm_provider

    return _create_llm_provider(
        model_default=model_default,
        model_legacy_names=model_legacy_names,
        temperature_default=temperature_default,
        max_tokens_default=max_tokens_default,
        timeout_default=timeout_default,
    )


def create_llm_provider_from_settings(settings) -> LLMProvider:
    from .factory import create_llm_provider_from_settings as _create_llm_provider_from_settings

    return _create_llm_provider_from_settings(settings)

__all__ = [
    "JSONValue",
    "LLMJsonSchema",
    "LLMMessage",
    "LLMProvider",
    "LLMRequestOptions",
    "OpenAIProvider",
    "create_llm_provider",
    "create_llm_provider_from_settings",
]

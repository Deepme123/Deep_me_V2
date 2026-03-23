from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Generator
from typing import Optional

from app.core.llm import (
    LLMMessage,
    LLMProvider,
    LLMRequestOptions,
    create_llm_provider_from_settings,
)
from app.core.llm_settings import LLMSettings, get_llm_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendLLMInfo:
    provider: str
    model: str


def _compose_system(system_prompt: str, task_prompt: Optional[str]) -> str:
    if task_prompt:
        return f"{system_prompt}\n\n---\n[Task Prompt]\n{task_prompt}"
    return system_prompt


def _build_messages(
    system_prompt: str,
    task_prompt: Optional[str],
    conversation: list[tuple[str, str]],
) -> list[LLMMessage]:
    messages = [
        LLMMessage(
            role="system",
            content=_compose_system(system_prompt, task_prompt),
        )
    ]
    for role, text in conversation:
        messages.append(
            LLMMessage(
                role="user" if role == "user" else "assistant",
                content=text or "",
            )
        )
    return messages


def _build_request_options(
    *,
    temperature: Optional[float],
    max_tokens: Optional[int],
    model: Optional[str],
) -> LLMRequestOptions:
    return LLMRequestOptions(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _get_backend_llm_settings() -> LLMSettings:
    return get_llm_settings(
        model_default="gpt-4o-mini",
        timeout_default=60.0,
    )


def _get_backend_llm_provider() -> LLMProvider:
    settings = _get_backend_llm_settings()
    return create_llm_provider_from_settings(settings)


def get_backend_llm_info(*, model: Optional[str] = None) -> BackendLLMInfo:
    settings = _get_backend_llm_settings()
    resolved_model = (model or settings.model).strip() or settings.model
    return BackendLLMInfo(
        provider=settings.provider,
        model=resolved_model,
    )


def stream_noa_response(
    *,
    system_prompt: str,
    task_prompt: Optional[str],
    conversation: list[tuple[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = 800,
    model: Optional[str] = None,
) -> Generator[str, None, None]:
    provider = _get_backend_llm_provider()
    messages = _build_messages(system_prompt, task_prompt, conversation)
    options = _build_request_options(
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    logger.debug("LLM stream request prepared | messages=%s model=%s", len(messages), model)
    yield from provider.stream_text(messages=messages, options=options)


def generate_noa_response(
    *,
    system_prompt: str,
    task_prompt: Optional[str],
    conversation: list[tuple[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = 800,
    model: Optional[str] = None,
) -> str:
    provider = _get_backend_llm_provider()
    messages = _build_messages(system_prompt, task_prompt, conversation)
    options = _build_request_options(
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    logger.debug("LLM text request prepared | messages=%s model=%s", len(messages), model)
    return provider.generate_text(messages=messages, options=options)

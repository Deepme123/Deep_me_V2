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
    # gpt-5.x reasoning 모델은 보이지 않는 추론 토큰도 max_output_tokens 예산을
    # 함께 소비한다. 분석카드 스키마(situation_steps/behavior_patterns/thoughts 등
    # 다수의 필수 필드)를 끝까지 채우기엔 1500이 너무 낮아 응답이 잘려 JSON 파싱이
    # 실패하고 빈 fallback 카드로 떨어지는 경우가 있었다.
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        max_tokens_default=4000,
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

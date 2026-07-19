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
    # CARD_MAX_TOKENS가 설정되어 있으면 공통 LLM_MAX_TOKENS보다 우선 적용된다 —
    # LLM_MAX_TOKENS는 채팅/태스크/욕구분석과 공유되는 값이라 그대로 두고
    # 분석카드만 별도로 늘릴 수 있어야 한다.
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        max_tokens_default=4000,
        max_tokens_override_names=("CARD_MAX_TOKENS",),
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
    # reflection_message(욕구별 2~4문장 한국어 서술) 필드가 8개 needs 각각에
    # 필수로 추가되면서 출력량이 늘었고, gpt-5.x reasoning 모델은 보이지 않는
    # 추론 토큰도 max_output_tokens 예산을 함께 소비한다. 공통 기본값 800으로는
    # 응답이 중간에 잘려 JSON 파싱이 실패하고 fallback 점수로 떨어지는 경우가
    # 있었다 (get_card_provider와 동일한 문제).
    # NEED_CARD_MAX_TOKENS가 설정되어 있으면 공통 LLM_MAX_TOKENS보다 우선 적용된다.
    return create_llm_provider(
        model_default="gpt-5.4-mini-2026-03-17",
        model_legacy_names=("NEED_CARD_MODEL",),
        max_tokens_default=3000,
        max_tokens_override_names=("NEED_CARD_MAX_TOKENS",),
        timeout_default=15.0,
    )

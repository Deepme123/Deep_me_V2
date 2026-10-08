from __future__ import annotations

import logging
from typing import List

from pydantic import ValidationError

from app.analyze import schemas as sc
from app.analyze.services.emotion_taxonomy import TAXONOMY_BLOCK
from app.analyze.services.llm_card_schema import CARD_SCHEMA
from app.analyze.services.llm_card_validation import (
    LLMCardPayload,
    validate_behavior_patterns,
    validate_emotion_entries,
    validate_physical_reactions,
    validate_thought_entries,
)
from app.analyze.services.prompt_loader import get_card_system_prompt
from app.core.llm import LLMMessage
from app.core.llm.providers import get_card_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = get_card_system_prompt(TAXONOMY_BLOCK)


def _format_dialogue(turns: List[sc.ConversationTurn]) -> str:
    lines: List[str] = []
    for turn in turns:
        speaker = turn.speaker.upper()
        if speaker == "USER":
            name = "User"
        elif speaker == "NOA":
            name = "Noa"
        else:
            name = speaker
        lines.append(f"{name}: {turn.text}")
    return "\n".join(lines)


def _build_fallback_card() -> sc.CardCreate:
    return sc.CardCreate()


def analyze_dialogue_to_card(
    turns: List[sc.ConversationTurn],
    title_hint: str | None = None,
    *,
    max_attempts: int = 2,
) -> sc.CardCreate:
    if not turns:
        raise ValueError("conversation_log is empty.")

    dialogue_text = _format_dialogue(turns)
    hint_block = f"Title hint: {title_hint}\n\n" if title_hint else ""
    user_prompt = (
        "Analyze the counseling conversation below and return only JSON that matches the schema.\n\n"
        "Output rule: keep schema keys in English, but write every summary, label, sentence, and list item in Korean.\n\n"
        f"{hint_block}"
        "[Conversation Start]\n"
        f"{dialogue_text}\n"
        "[Conversation End]"
    )

    last_exc: Exception | None = None
    # 트랜지언트 오류(네트워크, rate limit, JSON 잘림 등) 한 번으로 빈 fallback
    # 카드가 영구 저장되는 걸 막기 위해 한 번 더 시도해 본다.
    for attempt in range(1, max_attempts + 1):
        try:
            provider = get_card_provider()
            payload = provider.generate_json(
                messages=[
                    LLMMessage(role="system", content=_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                schema=CARD_SCHEMA,
            )
            structured = LLMCardPayload.model_validate(payload)
            validated_emotions = validate_emotion_entries(structured.core_emotions)
            # core_emotions에 실제로 존재하는 primary만 허용해, thoughts/physical_reactions/
            # behavior_patterns에 감정 탭에는 없는 새 감정 레이블이 새어나가는 것을 막는다.
            allowed_primaries = (
                frozenset(e.primary for e in validated_emotions)
                if validated_emotions
                else None
            )
            structured = structured.model_copy(
                update={
                    "core_emotions": validated_emotions,
                    "thoughts": validate_thought_entries(structured.thoughts, allowed_primaries),
                    "physical_reactions": validate_physical_reactions(
                        structured.physical_reactions, allowed_primaries
                    ),
                    "behavior_patterns": validate_behavior_patterns(
                        structured.behavior_patterns, allowed_primaries
                    ),
                }
            )
            return sc.CardCreate.model_validate(structured.model_dump())
        except (RuntimeError, ValidationError, ValueError, TypeError) as exc:
            last_exc = exc
            logger.warning(
                "LLM card analysis attempt %d/%d failed: %s", attempt, max_attempts, exc
            )

    logger.warning(
        "LLM card analysis failed after %d attempts, returning fallback card: %s",
        max_attempts,
        last_exc,
    )
    return _build_fallback_card()

from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analyze import schemas as sc
from app.analyze.config import settings
from app.core.llm import LLMJsonSchema, LLMMessage, create_llm_provider

logger = logging.getLogger(__name__)

_CARD_SCHEMA = LLMJsonSchema(
    name="emotion_card",
    schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "core_emotions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "situation": {"type": "string"},
            "emotion": {"type": "string"},
            "thoughts": {"type": "string"},
            "physical_reactions": {"type": "string"},
            "behaviors": {"type": "string"},
            "coping_actions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "insight": {"type": "string"},
        },
    },
)

_SYSTEM_PROMPT = """You are a psychologist who reads a counseling conversation and extracts a structured emotion card.
Return JSON only.

Field definitions:
- summary: one or two sentences summarizing the overall situation
- core_emotions: 1 to 3 dominant emotions
- situation: the user's surrounding context or trigger
- emotion: emotional state in natural language
- thoughts: notable thoughts or automatic thoughts
- physical_reactions: physical responses or sensations
- behaviors: observed actions or behavior tendencies
- coping_actions: concrete coping actions already attempted or available
- tags: short topical keywords
- insight: one or two sentences of useful insight
"""


class _LLMCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    core_emotions: list[str] | None = None
    situation: str | None = None
    emotion: str | None = None
    thoughts: str | None = None
    physical_reactions: str | None = None
    behaviors: str | None = None
    coping_actions: list[str] | None = None
    tags: list[str] | None = None
    insight: str | None = None


def _get_card_llm_provider():
    return create_llm_provider(
        model_default=settings.llm_model,
        temperature_default=settings.llm_temperature,
        max_tokens_default=settings.llm_max_tokens,
        timeout_default=settings.llm_timeout_sec,
    )


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
) -> sc.CardCreate:
    if not turns:
        raise ValueError("conversation_log is empty.")

    dialogue_text = _format_dialogue(turns)
    hint_block = f"Title hint: {title_hint}\n\n" if title_hint else ""
    user_prompt = (
        "Analyze the counseling conversation below and return only JSON that matches the schema.\n\n"
        f"{hint_block}"
        "[Conversation Start]\n"
        f"{dialogue_text}\n"
        "[Conversation End]"
    )

    try:
        provider = _get_card_llm_provider()
        payload = provider.generate_json(
            messages=[
                LLMMessage(role="system", content=_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            schema=_CARD_SCHEMA,
        )
        structured = _LLMCardPayload.model_validate(payload)
        return sc.CardCreate.model_validate(structured.model_dump())
    except (RuntimeError, ValidationError, ValueError, TypeError) as exc:
        logger.warning("LLM card analysis failed, returning fallback card: %s", exc)
        return _build_fallback_card()

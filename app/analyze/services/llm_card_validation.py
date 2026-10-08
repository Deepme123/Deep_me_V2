from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from app.analyze.services.emotion_taxonomy import VALID_PRIMARIES, VALID_SUBS

logger = logging.getLogger(__name__)

# quote 값이 LLM에 의해 따옴표로 감싸져 오거나 발화 원문에 따옴표가 포함된 경우,
# UI에서 다시 따옴표로 감싸면 중복(""...")이 발생한다. 저장 전에 감싸는 따옴표를 제거한다.
_WRAPPING_QUOTES = "\"'“”‘’「」『』"


def _strip_wrapping_quotes(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text.strip()
    # 앞뒤가 서로 대응하지 않아도, 감싸는 따옴표류 문자는 반복적으로 벗겨낸다.
    while len(cleaned) >= 2 and cleaned[0] in _WRAPPING_QUOTES and cleaned[-1] in _WRAPPING_QUOTES:
        cleaned = cleaned[1:-1].strip()
    return cleaned


class EmotionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str
    sub: list[str]
    quote: str | None = None
    reasoning: list[str] | None = None


def validate_emotion_entries(
    entries: list[EmotionEntry] | None,
) -> list[EmotionEntry] | None:
    if not entries:
        return entries
    valid = []
    for entry in entries:
        if entry.primary not in VALID_PRIMARIES:
            logger.warning("Unknown primary emotion %r — dropped", entry.primary)
            continue
        clean_subs = [s for s in entry.sub if s in VALID_SUBS[entry.primary]]
        if not clean_subs:
            logger.warning("No valid sub-emotions for %r — dropped", entry.primary)
            continue
        if len(clean_subs) != len(entry.sub):
            logger.warning("Invalid sub-emotions stripped for %r", entry.primary)
        valid.append(EmotionEntry(
            primary=entry.primary,
            sub=clean_subs,
            quote=_strip_wrapping_quotes(entry.quote),
            reasoning=entry.reasoning,
        ))
    return valid or None


class PhysicalReactionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str
    primary: str | None = None


class BehaviorPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    primary: str | None = None
    items: list[str]


def _clamp_optional_primary(
    primary: str | None,
    allowed_primaries: frozenset[str] | None,
) -> str | None:
    """taxonomy에 없거나 core_emotions에 없는 primary는 None으로 비운다."""
    if primary is None or primary not in VALID_PRIMARIES:
        return None
    if allowed_primaries is not None and primary not in allowed_primaries:
        return None
    return primary


def validate_physical_reactions(
    entries: list[PhysicalReactionItem] | None,
    allowed_primaries: frozenset[str] | None,
) -> list[PhysicalReactionItem] | None:
    if not entries:
        return entries
    return [
        PhysicalReactionItem(
            title=e.title,
            description=e.description,
            primary=_clamp_optional_primary(e.primary, allowed_primaries),
        )
        for e in entries
    ]


def validate_behavior_patterns(
    entries: list[BehaviorPattern] | None,
    allowed_primaries: frozenset[str] | None,
) -> list[BehaviorPattern] | None:
    if not entries:
        return entries
    return [
        BehaviorPattern(
            title=e.title,
            primary=_clamp_optional_primary(e.primary, allowed_primaries),
            items=e.items,
        )
        for e in entries
    ]


class SituationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str
    interpretations: list[str]


class ThoughtEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str
    quote: str | None = None
    thoughts: list[str]


def validate_thought_entries(
    entries: list[ThoughtEntry] | None,
    allowed_primaries: frozenset[str] | None = None,
) -> list[ThoughtEntry] | None:
    if not entries:
        return entries
    valid = [
        ThoughtEntry(
            primary=e.primary,
            quote=_strip_wrapping_quotes(e.quote),
            thoughts=e.thoughts,
        )
        for e in entries
        if e.primary in VALID_PRIMARIES
        and (allowed_primaries is None or e.primary in allowed_primaries)
    ]
    dropped = len(entries) - len(valid)
    if dropped:
        logger.warning(
            "Unknown or core_emotions-mismatched primary emotion in %d thought entries — dropped",
            dropped,
        )
    return valid or None


class LLMCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    core_emotions: list[EmotionEntry] | None = None
    situation: str | None = None
    situation_steps: list[SituationStep] | None = None
    physical_reactions: list[PhysicalReactionItem] | None = None
    behavior_patterns: list[BehaviorPattern] | None = None
    coping_actions: list[str] | None = None
    tags: list[str] | None = None
    insight: str | None = None
    thoughts: list[ThoughtEntry] | None = None

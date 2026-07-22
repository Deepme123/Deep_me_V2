from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analyze import schemas as sc
from app.analyze.services.prompt_loader import get_card_system_prompt
from app.core.llm import LLMJsonSchema, LLMMessage
from app.core.llm.providers import get_card_provider

logger = logging.getLogger(__name__)

_EMOTION_TAXONOMY: dict[str, list[str]] = {
    "기쁨": ["기쁜", "즐거운", "행복한", "유쾌한", "신나는", "황홀한", "들뜬", "흐뭇한", "희망찬", "감동받은", "상쾌한", "후련한"],
    "자신": ["자랑스러운", "의기양양한", "만족스러운", "뿌듯한", "당당한", "용기 나는", "든든한", "충만한"],
    "열정": ["영감을 받은", "동기 부여된", "활발한", "집중하는", "활기찬", "짜릿한", "기대에 부푼", "희망에 찬"],
    "감동": ["다정한", "감사하는", "감동적인", "고마운", "사랑하는", "뭉클한", "벅찬"],
    "편안": ["편안한", "고요한", "차분한", "여유로운", "나른한", "진정되는", "속편한"],
    "심심": ["따분한", "심심한", "지루한", "질린"],
    "피곤": ["피곤한", "지친", "힘든", "맥 빠진", "소모된", "무기력한", "기운 없는"],
    "담담": ["담담한", "차분한", "고요한", "진정되는", "생각에 잠긴", "의욕 없는", "멍한"],
    "고독": ["외로운", "쓸쓸한", "고독한", "소외된", "위축된", "공허한", "허전한", "허한"],
    "수치": ["멋쩍은", "쑥스러운", "부끄러운", "민망한", "당혹스러운", "창피한", "죄책감드는", "후회되는"],
    "우울": ["우울한", "서러운", "기죽은", "비참한", "절망한", "시무룩한", "섭섭한", "먹먹한", "속상한", "그리운"],
    "좌절": ["좌절한", "실망스러운", "언짢은", "불만족스러운", "막막한", "허탈한"],
    "혼란": ["뒤숭숭한", "혼란스러운", "놀란", "망연자실한", "어리둥절한"],
    "불안": ["불안한", "초조한", "긴장한", "안절부절못하는", "걱정되는", "겁나는", "두려운", "무서운", "예민한", "섬뜩한"],
    "분노": ["화난", "짜증나는", "답답한", "언짢은", "거슬리는", "불편한", "거북한", "억울한", "분한", "열 받는", "격노한"],
}

_VALID_PRIMARIES: frozenset[str] = frozenset(_EMOTION_TAXONOMY.keys())
_VALID_SUBS: dict[str, frozenset[str]] = {
    p: frozenset(subs) for p, subs in _EMOTION_TAXONOMY.items()
}


def _build_taxonomy_block() -> str:
    lines = ["[감정 분류 체계 — 반드시 아래 목록에서만 선택]"]
    for primary, subs in _EMOTION_TAXONOMY.items():
        lines.append(f"- {primary}: {', '.join(subs)}")
    return "\n".join(lines)


_TAXONOMY_BLOCK: str = _build_taxonomy_block()

_CARD_SCHEMA = LLMJsonSchema(
    name="analysis_card",
    schema={
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "core_emotions",
            "situation",
            "situation_steps",
            "physical_reactions",
            "behavior_patterns",
            "tags",
            "insight",
            "thoughts",
        ],
        "properties": {
            "summary": {"type": "string", "maxLength": 20},
            "core_emotions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": "string"},
                        "sub": {"type": "array", "items": {"type": "string"}},
                        "quote": {"type": "string"},
                        "reasoning": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["primary", "sub", "quote", "reasoning"],
                },
            },
            "situation": {"type": "string"},
            "situation_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "interpretations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["title", "description", "interpretations"],
                },
                "minItems": 1,
                "maxItems": 2,
            },
            "physical_reactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "primary": {"type": "string"},
                    },
                    "required": ["title", "description", "primary"],
                },
                "minItems": 1,
                "maxItems": 4,
            },
            "behavior_patterns": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "primary": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["title", "primary", "items"],
                },
            },
            "coping_actions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "insight": {"type": "string"},
            "thoughts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": "string"},
                        "quote": {"type": "string"},
                        "thoughts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 3,
                        },
                    },
                    "required": ["primary", "quote", "thoughts"],
                },
                "minItems": 1,
                "maxItems": 3,
            },
        },
    },
)

_SYSTEM_PROMPT = get_card_system_prompt(_TAXONOMY_BLOCK)


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


class _EmotionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str
    sub: list[str]
    quote: str | None = None
    reasoning: list[str] | None = None


def _validate_emotion_entries(
    entries: list[_EmotionEntry] | None,
) -> list[_EmotionEntry] | None:
    if not entries:
        return entries
    valid = []
    for entry in entries:
        if entry.primary not in _VALID_PRIMARIES:
            logger.warning("Unknown primary emotion %r — dropped", entry.primary)
            continue
        clean_subs = [s for s in entry.sub if s in _VALID_SUBS[entry.primary]]
        if not clean_subs:
            logger.warning("No valid sub-emotions for %r — dropped", entry.primary)
            continue
        if len(clean_subs) != len(entry.sub):
            logger.warning("Invalid sub-emotions stripped for %r", entry.primary)
        valid.append(_EmotionEntry(
            primary=entry.primary,
            sub=clean_subs,
            quote=_strip_wrapping_quotes(entry.quote),
            reasoning=entry.reasoning,
        ))
    return valid or None


class _PhysicalReactionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str
    primary: str | None = None


class _BehaviorPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    primary: str | None = None
    items: list[str]


def _clamp_optional_primary(
    primary: str | None,
    allowed_primaries: frozenset[str] | None,
) -> str | None:
    """taxonomy에 없거나 core_emotions에 없는 primary는 None으로 비운다."""
    if primary is None or primary not in _VALID_PRIMARIES:
        return None
    if allowed_primaries is not None and primary not in allowed_primaries:
        return None
    return primary


def _validate_physical_reactions(
    entries: list[_PhysicalReactionItem] | None,
    allowed_primaries: frozenset[str] | None,
) -> list[_PhysicalReactionItem] | None:
    if not entries:
        return entries
    return [
        _PhysicalReactionItem(
            title=e.title,
            description=e.description,
            primary=_clamp_optional_primary(e.primary, allowed_primaries),
        )
        for e in entries
    ]


def _validate_behavior_patterns(
    entries: list[_BehaviorPattern] | None,
    allowed_primaries: frozenset[str] | None,
) -> list[_BehaviorPattern] | None:
    if not entries:
        return entries
    return [
        _BehaviorPattern(
            title=e.title,
            primary=_clamp_optional_primary(e.primary, allowed_primaries),
            items=e.items,
        )
        for e in entries
    ]


class _SituationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str
    interpretations: list[str]


class _ThoughtEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str
    quote: str | None = None
    thoughts: list[str]


def _validate_thought_entries(
    entries: list[_ThoughtEntry] | None,
    allowed_primaries: frozenset[str] | None = None,
) -> list[_ThoughtEntry] | None:
    if not entries:
        return entries
    valid = [
        _ThoughtEntry(
            primary=e.primary,
            quote=_strip_wrapping_quotes(e.quote),
            thoughts=e.thoughts,
        )
        for e in entries
        if e.primary in _VALID_PRIMARIES
        and (allowed_primaries is None or e.primary in allowed_primaries)
    ]
    dropped = len(entries) - len(valid)
    if dropped:
        logger.warning(
            "Unknown or core_emotions-mismatched primary emotion in %d thought entries — dropped",
            dropped,
        )
    return valid or None


class _LLMCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    core_emotions: list[_EmotionEntry] | None = None
    situation: str | None = None
    situation_steps: list[_SituationStep] | None = None
    physical_reactions: list[_PhysicalReactionItem] | None = None
    behavior_patterns: list[_BehaviorPattern] | None = None
    coping_actions: list[str] | None = None
    tags: list[str] | None = None
    insight: str | None = None
    thoughts: list[_ThoughtEntry] | None = None



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
                schema=_CARD_SCHEMA,
            )
            structured = _LLMCardPayload.model_validate(payload)
            validated_emotions = _validate_emotion_entries(structured.core_emotions)
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
                    "thoughts": _validate_thought_entries(structured.thoughts, allowed_primaries),
                    "physical_reactions": _validate_physical_reactions(
                        structured.physical_reactions, allowed_primaries
                    ),
                    "behavior_patterns": _validate_behavior_patterns(
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

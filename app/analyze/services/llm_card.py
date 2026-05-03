from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analyze import schemas as sc
from app.analyze.config import get_settings
from app.core.llm import LLMJsonSchema, LLMMessage, create_llm_provider

logger = logging.getLogger(__name__)

_EMOTION_TAXONOMY: dict[str, list[str]] = {
    "기쁨": ["기쁜", "즐거운", "행복한", "유쾌한", "신나는", "황홀한", "들뜬", "흐뭇한", "희망찬", "감동받은", "상쾌한", "후련한"],
    "자신": ["자랑스러운", "의기양양한", "만족스러운", "뿌듯한", "당당한", "용기 나는", "든든한", "충만한"],
    "열정": ["영감을 받은", "동기 부여된", "활발한", "집중하는", "활기찬", "짜릿한", "기대에 부푼", "희망에 찬"],
    "감동": ["다정한", "감사하는", "감동적인", "고마운", "사랑하는", "뭉클한", "벅찬"],
    "편안": ["편안한", "고요한", "차분한", "여유로운", "나른한", "진정되는", "속편한"],
    "심심": ["따분한", "심심한", "지루한", "질린"],
    "피곤": ["피곤한", "지친", "힘든", "맥 빠진", "소모된"],
    "담담": ["담담한", "차분한", "고요한", "진정되는", "생각에 잠긴", "의욕 없는"],
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
        "properties": {
            "summary": {"type": "string"},
            "core_emotions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "primary": {"type": "string"},
                        "sub": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["primary", "sub"],
                },
            },
            "situation": {"type": "string"},
            "emotion": {"type": "string"},
            "thoughts": {"type": "string"},
            "physical_reactions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
            },
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

_SYSTEM_PROMPT = f"""You are a psychologist who reads a counseling conversation and extracts a structured emotion card.
Return JSON only. Keep the JSON field names exactly as provided in the schema. Write every string value in Korean.

{_TAXONOMY_BLOCK}

Field definitions:
- summary: 전체 상황을 요약하는 1~2문장
- core_emotions: 1~3개의 감정 항목. 각 항목은 반드시:
    * "primary": 위 목록의 상위감정 레이블 중 정확히 하나
    * "sub": 해당 상위감정 하위 목록에서만 고른 1개 이상의 감정 레이블
  목록에 없는 레이블은 절대 사용하지 말 것.
- situation: 사용자의 주변 상황 또는 촉발 요인
- emotion: 자연어로 표현한 감정 상태 (자유 형식)
- thoughts: 주요 생각 또는 자동적 사고
- physical_reactions: 신체 반응 또는 감각을 항목별로 나열 (최소 1개, 최대 4개). 4개를 초과할 경우 가장 두드러진 반응 4개만 추려서 출력.
- behaviors: 행동 경향 또는 관찰된 행동
- coping_actions: 시도했거나 가능한 대처 행동
- tags: 짧은 주제 키워드
- insight: 유용한 인사이트 1~2문장
"""


class _EmotionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: str
    sub: list[str]


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
        valid.append(_EmotionEntry(primary=entry.primary, sub=clean_subs))
    return valid or None


class _LLMCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    core_emotions: list[_EmotionEntry] | None = None
    situation: str | None = None
    emotion: str | None = None
    thoughts: str | None = None
    physical_reactions: list[str] | None = None
    behaviors: str | None = None
    coping_actions: list[str] | None = None
    tags: list[str] | None = None
    insight: str | None = None


def _get_card_llm_provider():
    settings = get_settings()
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
        "Output rule: keep schema keys in English, but write every summary, label, sentence, and list item in Korean.\n\n"
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
        structured = structured.model_copy(
            update={"core_emotions": _validate_emotion_entries(structured.core_emotions)}
        )
        return sc.CardCreate.model_validate(structured.model_dump())
    except (RuntimeError, ValidationError, ValueError, TypeError) as exc:
        logger.warning("LLM card analysis failed, returning fallback card: %s", exc)
        return _build_fallback_card()

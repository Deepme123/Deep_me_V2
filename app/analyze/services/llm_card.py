from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analyze import schemas as sc
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

_SYSTEM_PROMPT = f"""You are a warm, empathetic counselor who reads a counseling conversation and extracts a structured emotion card.
Return JSON only. Keep the JSON field names exactly as provided in the schema. Write every string value in Korean.

톤 원칙:
- 사용자 발화를 직접 인용하거나 그 말을 그대로 살려서 표현할 것
- 일반론적 조언이나 평가 문장 금지 (예: "이런 감정은 자연스러운 것입니다" X)
- 사용자 관점에서 관찰자가 바라보듯, 공감적이고 구체적으로 서술할 것
- 모든 서술은 사용자가 실제로 경험한 내용에 근거할 것

{_TAXONOMY_BLOCK}

Field definitions:
- summary: 대화의 핵심을 사용자 경험 중심으로 요약한 짧은 제목. 반드시 20자 이내로 작성할 것. 사용자가 직접 한 말의 뉘앙스를 살릴 것.
- core_emotions: 1~3개의 감정 항목. 각 항목은 반드시:
    * "primary": 위 목록의 상위감정 레이블 중 정확히 하나
    * "sub": 해당 상위감정 하위 목록에서만 고른 1개 이상의 감정 레이블
    * "quote": 해당 감정이 가장 잘 드러난 사용자 발화를 원문 그대로 인용 (사용자가 실제로 한 말)
    * "reasoning": 그 감정 상태를 구체적으로 묘사하는 문장 1~3개. 사용자 발화를 살려 서술하며, 평가나 조언 없이 경험을 그대로 담을 것.
  목록에 없는 레이블은 절대 사용하지 말 것.
- situation: 감정을 촉발한 구체적인 상황을 1~2문장으로. 사용자가 실제로 처한 맥락을 구체적으로 담을 것.
- situation_steps: 대화에서 드러난 구체적인 상황 요소를 1~2개 카드로 구성. 각 항목은:
    * "title": 해당 상황을 한 줄로 요약 (명사형 또는 짧은 절). 사용자 발화에서 직접 따올 것. (예: "애인의 답이 늦고 더 이상 찾지 않음")
    * "description": 그 상황에서 사용자가 어떻게 느끼고 반응했는지 1문장. 사용자 말투를 살려 1인칭 서술체로. (예: "마음이 멀어진 것 같아, 나만 애쓰고 있는 기분이 들었어")
    * "interpretations": 해당 상황에 대한 AI 해석 문장 정확히 3개. 서로 다른 관점(감정적·인지적·관계적)에서 각각 1문장. 사용자 경험에 밀착해 서술하며 일반론 금지.
- physical_reactions: 신체 반응을 최소 1개, 최대 4개. 각 항목은:
    * "title": 신체 반응 이름 (예: "가슴이 조여옴")
    * "description": 그 반응이 나타난 맥락을 사용자 경험 기준으로 1문장. (예: "전하고 싶은 말이 막혀서 가슴이 답답했어")
    * "primary": 이 신체 반응과 연관된 상위감정 레이블 (위 목록에서 하나)
- behavior_patterns: Noa가 행동에 대해 질문한 턴과 사용자 답변 턴만을 기반으로 생성.
    행동 관련 질문-답변이 없을 경우 대화에서 가장 구체적인 행동 묘사를 기반으로 생성.
    유동적으로 1~3개의 패턴 그룹으로 구성하며 각 그룹은:
    * "title": 해당 행동 패턴을 한 줄로 요약한 제목. 감정 상태와 행동의 관계를 담아 명사형으로 서술. (예: "기분이 가라앉으면 행동이 멈춤")
    * "primary": 이 행동 패턴과 연관된 상위감정 레이블 (위 목록에서 하나)
    * "items": 그 패턴에 해당하는 구체적 행동을 1~3개. 과거형 서술체로 작성. (예: "해야 할 일을 미루고 침대에 누워 있었다")
- coping_actions: 시도했거나 가능한 대처 행동
- tags: 짧은 주제 키워드
- insight: 사용자 경험에서 발견되는 패턴이나 강점을 1~2문장으로. 일반론 금지, 이 대화에서만 보이는 것을 담을 것.
- thoughts: 1~3개의 감정별 생각 그룹. 각 항목은 반드시:
    * "primary": 위 목록의 상위감정 레이블 중 정확히 하나
    * "quote": 사용자 발화를 원문 그대로 붙여넣지 말 것. 그 생각이 드러난 사용자 발화를 노아가 대신 전해주는 말투로 자연스럽게 재서술할 것. 반드시 사용자를 주어로 한 과거형 종결체("~했어", "~였어")로 끝맺을 것. (예: "취업 준비가 길어지는 게 조급해서 불안했어")
    * "thoughts": 그 감정을 겪을 때 사용자의 내면 생각을 1~3개 문장으로. 반드시 사용자 본인의 1인칭 독백체("나는~", "내가~")로 작성할 것. 관찰자/분석자 시점의 3인칭 서술("사용자는~", "스스로를 ~하게 해석하고 있다")은 절대 쓰지 말 것. 사용자가 마음속으로 스스로에게 실제로 하고 있을 법한 말을 그대로 옮길 것. (예: "내가 가는 길이 맞는지 확신이 안 서.", "남들은 벌써 자리를 잡았는데 나만 뒤처진 것 같아.") 일반론 금지.
  목록에 없는 레이블은 절대 사용하지 말 것.
"""


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
            quote=entry.quote,
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
) -> list[_ThoughtEntry] | None:
    if not entries:
        return entries
    valid = [e for e in entries if e.primary in _VALID_PRIMARIES]
    dropped = len(entries) - len(valid)
    if dropped:
        logger.warning("Unknown primary emotion in %d thought entries — dropped", dropped)
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
            structured = structured.model_copy(
                update={
                    "core_emotions": _validate_emotion_entries(structured.core_emotions),
                    "thoughts": _validate_thought_entries(structured.thoughts),
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

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlmodel import Session

from app.core.llm import LLMJsonSchema, LLMMessage
from app.desire.core.needs_definitions import NEEDS_METADATA, NeedCode
from app.desire.crud.need_card import get_recent_user_need_selections, save_need_card_result
from app.desire.models.need_card import UserNeedSelection
from app.desire.schemas.need_card import NeedCardResponse, NeedScore
from app.desire.services.llm_client import get_llm_provider
from app.desire.services.reflection_writer import generate_reflection_messages

logger = logging.getLogger(__name__)

DEFAULT_NEED_SCORE = 50
NEED_CODES = [code.value for code in NeedCode]

SYSTEM_PROMPT = """\
You are a psychologist who extracts motivational needs from a conversation.
Rate all 8 needs and rank them from strongest (1) to weakest (8) with no ties.
Definitions:
- Choice: autonomy, agency, preference, ability to decide and set direction.
- Safe: stability, predictability, protection, freedom from risk or harm.
- Together: belonging, connection, collaborating, feeling included.
- Fun: playfulness, joy, novelty, lightness.
- Meaning: purpose, contribution, impact that matters.
- True: honesty, authenticity, directness, facts as they are.
- Peace: calm, balance, rest, absence of conflict.
- Grow: learning, challenge, improvement, stretching limits.
Scores should align with ranks (higher rank => higher score) and reflect only the provided conversation."""

USER_PROMPT_TEMPLATE = """\
Analyze the following conversation and return structured JSON only.
Conversation:
---
{conversation_text}
---
{personalization_section}Rules:
- Include exactly one entry for every need code: Choice, Safe, Together, Fun, Meaning, True, Peace, Grow.
- Rank 1 means the most dominant need in this conversation context, 8 the least.
- For every need, write "rationale" in Korean (2~3문장): 대화 속 어떤 발화·맥락에서 이 욕구가 드러났는지 구체적으로 설명할 것. 일반론 금지, 이 대화에 실제로 나타난 신호에 근거할 것."""

RESPONSE_JSON_SCHEMA = LLMJsonSchema(
    name="need_analysis",
    schema={
        "type": "object",
        "properties": {
            "needs": {
                "type": "array",
                "minItems": 8,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "score", "rank", "rationale"],
                    "properties": {
                        "code": {"type": "string", "enum": NEED_CODES},
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "rank": {"type": "integer", "minimum": 1, "maximum": 8},
                        "rationale": {"type": "string"},
                    },
                },
            }
        },
        "required": ["needs"],
        "additionalProperties": False,
    },
)


class LLMNeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: NeedCode
    score: int = Field(ge=0, le=100)
    rank: int = Field(ge=1, le=8)
    rationale: str = ""

    @model_validator(mode="after")
    def clamp_values(self) -> "LLMNeedItem":
        clamped_score = max(0, min(100, int(self.score)))
        clamped_rank = max(1, min(8, int(self.rank)))
        return self.model_copy(update={"score": clamped_score, "rank": clamped_rank})


class LLMNeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs: List[LLMNeedItem]

    @model_validator(mode="after")
    def ensure_need_completeness(self) -> "LLMNeedResponse":
        if len(self.needs) < 8:
            raise ValueError("LLM returned fewer than 8 needs.")
        return self


def _build_need_scores(items: List[LLMNeedItem]) -> List[NeedScore]:
    best_by_code: Dict[NeedCode, LLMNeedItem] = {}
    for item in items:
        current = best_by_code.get(item.code)
        if current is None:
            best_by_code[item.code] = item
            continue
        if item.rank < current.rank or (item.rank == current.rank and item.score > current.score):
            best_by_code[item.code] = item

    for code in NeedCode:
        if code not in best_by_code:
            best_by_code[code] = LLMNeedItem(
                code=code,
                score=DEFAULT_NEED_SCORE,
                rank=99,
                rationale="Added by server because the model omitted this need.",
            )

    ordered_items = sorted(
        best_by_code.values(),
        key=lambda item: (item.rank, -item.score, item.code.value),
    )

    needs: List[NeedScore] = []
    for idx, item in enumerate(ordered_items, start=1):
        meta = NEEDS_METADATA[item.code]
        needs.append(
            NeedScore(
                code=item.code,
                label_ko=meta["label_ko"],
                label_en=meta["label_en"],
                score=item.score,
                rank=idx,
                rationale=item.rationale,
            )
        )

    return needs


MIN_FREQUENT_SELECTION_COUNT = 2


def _build_personalization_hint(selections: List[UserNeedSelection]) -> str:
    """과거 유저 선택 이력을 빈도 집계해 참고용 힌트 문장을 만든다.

    2회 이상 선택된 욕구가 없으면(전부 1회씩 동률 등) "자주 선택했다"고
    부를 근거가 없으므로 힌트를 만들지 않는다.
    """
    counts: Dict[str, int] = {}
    for selection in selections:
        for code in selection.selected_codes:
            counts[code] = counts.get(code, 0) + 1

    frequent = {code: count for code, count in counts.items() if count >= MIN_FREQUENT_SELECTION_COUNT}
    if not frequent:
        return ""

    top_codes = sorted(frequent.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
    labels = [NEEDS_METADATA[NeedCode(code)]["label_ko"] for code, _ in top_codes]
    return f"이 사용자가 과거 세션에서 자주 선택한 욕구: {', '.join(labels)}."


def _resolve_personalization_hint(db: Session, session_id: UUID) -> str:
    from app.backend.models.emotion import EmotionSession

    try:
        session_row = db.get(EmotionSession, session_id)
        if session_row is None or session_row.user_id is None:
            return ""
        selections = get_recent_user_need_selections(db, session_row.user_id)
        return _build_personalization_hint(selections)
    except Exception as exc:
        logger.warning("Failed to resolve personalization hint: %s", exc)
        db.rollback()
        return ""


def _call_llm(conversation_text: str, personalization_hint: str = "") -> List[NeedScore]:
    try:
        provider = get_llm_provider()
        personalization_section = (
            f"참고용 사용자 성향 힌트(참고만 할 것 — 이번 대화 내용이 항상 최우선 근거임): "
            f"{personalization_hint}\n"
            if personalization_hint
            else ""
        )
        payload = provider.generate_json(
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=USER_PROMPT_TEMPLATE.format(
                        conversation_text=conversation_text,
                        personalization_section=personalization_section,
                    ),
                ),
            ],
            schema=RESPONSE_JSON_SCHEMA,
        )
        structured = LLMNeedResponse.model_validate(payload)
        return _build_need_scores(structured.needs)
    except (RuntimeError, ValidationError, ValueError, TypeError) as exc:
        logger.warning("LLM need analysis failed, will fall back to defaults: %s", exc)
        raise


def _fallback_need_scores() -> List[NeedScore]:
    fallback_items: List[NeedScore] = []
    for idx, code in enumerate(NeedCode, start=1):
        meta = NEEDS_METADATA[code]
        fallback_items.append(
            NeedScore(
                code=code,
                label_ko=meta["label_ko"],
                label_en=meta["label_en"],
                score=DEFAULT_NEED_SCORE,
                rank=idx,
            )
        )
    return fallback_items


def analyze_needs_sync(
    conversation_text: str,
    session_id: UUID,
    db: Session,
) -> NeedCardResponse:
    """개인화 힌트 조회 → LLM 채점(실패 시 폴백) → 저장을 단일 스레드 호출로 원자적으로 수행한다.

    REST(analyze_needs)와 WS(ws_post_actions.generate_need_card_async) 양쪽이 이 함수를
    각각 하나의 threadpool 호출로만 감싸 써야 한다 — 별도 await 경계로 쪼개면, 타임아웃으로
    인한 취소가 "LLM 호출은 끝났지만 저장은 아직 안 된" 틈에 끼어들어 계산된 결과가
    저장되지 못한 채 유실될 수 있다.
    """
    personalization_hint = _resolve_personalization_hint(db, session_id)
    try:
        need_scores = _call_llm(conversation_text, personalization_hint)
    except Exception as exc:
        logger.error("Using fallback need scores because analysis failed: %s", exc)
        need_scores = _fallback_need_scores()

    top4 = need_scores[:4]
    reflections = generate_reflection_messages(db, session_id, [item.label_ko for item in top4])
    for item in top4:
        if item.label_ko in reflections:
            item.reflection_message = reflections[item.label_ko]

    save_need_card_result(db, session_id, need_scores)

    return NeedCardResponse(needs=need_scores, top4=top4)


async def analyze_needs(
    conversation_text: str,
    session_id: UUID,
    db: Session,
) -> NeedCardResponse:
    return await run_in_threadpool(analyze_needs_sync, conversation_text, session_id, db)

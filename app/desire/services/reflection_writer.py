from __future__ import annotations

import logging
from typing import Dict, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.core.llm import LLMJsonSchema, LLMMessage
from app.desire.core.prompt_loader import (
    get_reflection_system_prompt,
    get_reflection_user_prompt_template,
)
from app.desire.services.llm_client import get_llm_provider

logger = logging.getLogger(__name__)

EMOTION_KEYWORDS_LIMIT = 6


def _fetch_analysis_card(session: Session, session_id: UUID):
    from app.analyze.models import AnalysisCard

    stmt = select(AnalysisCard).where(AnalysisCard.session_id == session_id)
    return session.exec(stmt).first()


def _conversation_summary_and_keywords(card) -> tuple[str, str]:
    """AnalysisCard.situation을 요약으로, core_emotions의 primary/sub를 감정 키워드로 평탄화한다."""
    summary = (card.situation or "").strip()

    keywords: List[str] = []
    for entry in card.core_emotions or []:
        if not isinstance(entry, dict):
            continue
        primary = entry.get("primary")
        if primary and primary not in keywords:
            keywords.append(primary)
        for sub in entry.get("sub") or []:
            if sub and sub not in keywords:
                keywords.append(sub)

    return summary, ", ".join(keywords[:EMOTION_KEYWORDS_LIMIT])


class _ReflectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desire: str
    paragraph_1: str
    paragraph_2: str


class _ReflectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reflections: List[_ReflectionItem]


def _build_schema(desire_labels: List[str]) -> LLMJsonSchema:
    return LLMJsonSchema(
        name="need_card_reflection",
        schema={
            "type": "object",
            "properties": {
                "reflections": {
                    "type": "array",
                    "minItems": len(desire_labels),
                    "maxItems": len(desire_labels),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["desire", "paragraph_1", "paragraph_2"],
                        "properties": {
                            "desire": {"type": "string", "enum": desire_labels},
                            "paragraph_1": {"type": "string"},
                            "paragraph_2": {"type": "string"},
                        },
                    },
                }
            },
            "required": ["reflections"],
            "additionalProperties": False,
        },
    )


def generate_reflection_messages(
    db: Session,
    session_id: UUID,
    desire_labels: List[str],
) -> Dict[str, str]:
    """top4 욕구 각각에 대해 개인화된 2단락 reflection_message를 생성한다.

    AnalysisCard가 없거나 LLM 호출/파싱이 실패하면 빈 dict를 반환한다 —
    호출부는 누락된 label에 대해 빈 문자열을 쓰면 된다. score/rank/rationale
    저장이라는 주 흐름을 절대 막지 않기 위해 예외를 여기서 전부 흡수한다.
    """
    if not desire_labels:
        return {}

    try:
        card = _fetch_analysis_card(db, session_id)
        if card is None:
            return {}

        conversation_summary, emotion_keywords = _conversation_summary_and_keywords(card)
        if not conversation_summary and not emotion_keywords:
            return {}

        provider = get_llm_provider()
        user_prompt = get_reflection_user_prompt_template().format(
            desire_list=", ".join(desire_labels),
            conversation_summary=conversation_summary,
            emotion_keywords=emotion_keywords,
        )
        payload = provider.generate_json(
            messages=[
                LLMMessage(role="system", content=get_reflection_system_prompt()),
                LLMMessage(role="user", content=user_prompt),
            ],
            schema=_build_schema(desire_labels),
        )
        structured = _ReflectionResponse.model_validate(payload)
        return {
            item.desire: f"{item.paragraph_1}\n\n{item.paragraph_2}"
            for item in structured.reflections
            if item.desire in desire_labels
        }
    except Exception as exc:
        logger.warning("Failed to generate need card reflection messages: %s", exc)
        db.rollback()
        return {}

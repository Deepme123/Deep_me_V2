import json
import logging
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool
from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.desire.core.needs_definitions import NeedCode, NEEDS_METADATA
from app.desire.schemas.need_card import NeedCardResponse, NeedScore
from app.desire.services.llm_client import client, get_model_name

logger = logging.getLogger(__name__)

# LLM invocation settings
LLM_TIMEOUT_SECONDS = 15
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
Rules:
- Include exactly one entry for every need code: Choice, Safe, Together, Fun, Meaning, True, Peace, Grow.
- Rank 1 means the most dominant need in this conversation context, 8 the least.
- Provide a short rationale citing signals from the text."""

RESPONSE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "need_analysis",
        "schema": {
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
        "strict": True,
    },
}


class LLMNeedItem(BaseModel):
    code: NeedCode
    score: int = Field(ge=0, le=100)
    rank: int = Field(ge=1, le=8)
    rationale: str = ""

    @model_validator(mode="after")
    def clamp_values(self) -> "LLMNeedItem":
        # Defensive clamping in case the model returns edges.
        clamped_score = max(0, min(100, int(self.score)))
        clamped_rank = max(1, min(8, int(self.rank)))
        return self.model_copy(update={"score": clamped_score, "rank": clamped_rank})


class LLMNeedResponse(BaseModel):
    needs: List[LLMNeedItem]

    @model_validator(mode="after")
    def ensure_need_completeness(self) -> "LLMNeedResponse":
        if len(self.needs) < 8:
            raise ValueError("LLM returned fewer than 8 needs.")
        return self


def _build_need_scores(items: List[LLMNeedItem]) -> List[NeedScore]:
    # Pick the best entry per need code (lowest rank wins, tie-break by higher score).
    best_by_code: Dict[NeedCode, LLMNeedItem] = {}
    for item in items:
        current = best_by_code.get(item.code)
        if current is None:
            best_by_code[item.code] = item
            continue
        if item.rank < current.rank or (item.rank == current.rank and item.score > current.score):
            best_by_code[item.code] = item

    # Fill missing needs with a neutral baseline so the API never breaks.
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
        key=lambda i: (i.rank, -i.score, i.code.value),
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
            )
        )

    return needs


def _extract_response_text(response: Any) -> str:
    # The OpenAI responses endpoint exposes convenience helpers; fall back to raw content.
    if getattr(response, "output_text", None):
        return response.output_text

    if getattr(response, "choices", None):
        choice = response.choices[0]
        return getattr(choice.message, "content", "") or ""

    if getattr(response, "output", None):
        fragments: List[str] = []
        for block in response.output:
            for content in getattr(block, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    fragments.append(text)
        if fragments:
            return "".join(fragments)

    raise ValueError("Unable to read content from OpenAI response.")


def _call_llm(conversation_text: str) -> List[NeedScore]:
    try:
        response = client.responses.create(
            model=get_model_name(),
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(conversation_text=conversation_text)},
            ],
            response_format=RESPONSE_JSON_SCHEMA,
            temperature=0.1,
            max_output_tokens=800,
            timeout=LLM_TIMEOUT_SECONDS,
        )

        raw_text = _extract_response_text(response)
        parsed = json.loads(raw_text)
        structured = LLMNeedResponse.model_validate(parsed)
        return _build_need_scores(structured.needs)

    except (OpenAIError, ValidationError, json.JSONDecodeError, ValueError) as exc:
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


async def analyze_needs(conversation_text: str) -> NeedCardResponse:
    """
    Entry point for the need-card analyzer.
    Uses the OpenAI client with a structured JSON prompt, falls back to neutral defaults on failure.
    """
    try:
        need_scores = await run_in_threadpool(_call_llm, conversation_text)
    except Exception as exc:
        # Keep the API healthy even if OpenAI is unavailable.
        logger.error("Using fallback need scores because analysis failed: %s", exc)
        need_scores = _fallback_need_scores()

    top4 = need_scores[:4]
    return NeedCardResponse(needs=need_scores, top4=top4)

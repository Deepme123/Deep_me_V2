from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.desire.core.needs_definitions import NEEDS_METADATA, NeedCode


class NeedCardRequest(BaseModel):
    """User conversation payload for need analysis."""

    session_id: UUID = Field(..., description="EmotionSession ID to link results to")
    conversation_text: str = Field(..., description="Full conversation text to analyze")


class NeedScore(BaseModel):
    code: NeedCode
    label_ko: str
    label_en: str
    score: int = Field(..., ge=0, le=100, description="Score between 0 and 100")
    rank: int = Field(..., ge=1, le=8, description="1=highest priority need, 8=lowest")
    rationale: str = Field(default="", description="이 욕구 점수의 근거 설명")
    reflection_message: str = Field(default="", description="욕구 카드 선택 시 보여줄 개인화된 서술 문단")
    creature_name_ko: str = ""
    creature_emoji: str = ""
    creature_description: str = ""

    class Config:
        use_enum_values = True


class NeedCardResponse(BaseModel):
    """Eight needs with scores and ranking plus top-4 convenience slice."""

    needs: List[NeedScore]
    top4: List[NeedScore]

    @classmethod
    def from_scores(
        cls,
        scores_by_code: dict[str, int],
        rationales_by_code: dict[str, str] | None = None,
    ) -> "NeedCardResponse":
        items = []
        rationales_by_code = rationales_by_code or {}
        sorted_codes = sorted(
            scores_by_code.keys(),
            key=lambda c: scores_by_code[c],
            reverse=True,
        )

        for idx, code_str in enumerate(sorted_codes, start=1):
            code = NeedCode(code_str)
            meta = NEEDS_METADATA[code]
            items.append(
                NeedScore(
                    code=code,
                    label_ko=meta["label_ko"],
                    label_en=meta["label_en"],
                    score=int(scores_by_code[code_str]),
                    rank=idx,
                    rationale=rationales_by_code.get(code_str, ""),
                    creature_name_ko=meta.get("creature_name_ko", ""),
                    creature_emoji=meta.get("creature_emoji", ""),
                    creature_description=meta.get("creature_description", ""),
                )
            )

        top4 = items[:4]
        return cls(needs=items, top4=top4)


class NeedDetail(BaseModel):
    code: NeedCode
    label_ko: str
    label_en: str
    description: str
    icon: str
    creature_name_ko: str = ""
    creature_emoji: str = ""
    creature_description: str = ""

    class Config:
        use_enum_values = True


class NeedListResponse(BaseModel):
    needs: List[NeedDetail]

    @classmethod
    def all(cls) -> "NeedListResponse":
        needs = [
            NeedDetail(
                code=code,
                label_ko=meta["label_ko"],
                label_en=meta["label_en"],
                description=meta["description"],
                icon=meta.get("icon", ""),
            )
            for code, meta in NEEDS_METADATA.items()
        ]
        return cls(needs=needs)


class NeedCardHistoryItem(BaseModel):
    result_id: UUID
    session_id: UUID
    created_at: datetime
    top4: List[NeedScore]

    model_config = {"from_attributes": True}


class NeedCardHistoryResponse(BaseModel):
    items: List[NeedCardHistoryItem]
    total: int


class NeedSelectionRequest(BaseModel):
    selected_need: NeedCode = Field(..., description="Selected need code")

    class Config:
        use_enum_values = True


class NeedSelectionResponse(NeedDetail):
    @classmethod
    def from_code(cls, code: str) -> "NeedSelectionResponse":
        meta = NEEDS_METADATA.get(NeedCode(code))
        if not meta:
            raise ValueError(f"Unknown need code: {code}")
        return cls(
            code=NeedCode(code),
            label_ko=meta["label_ko"],
            label_en=meta["label_en"],
            description=meta["description"],
            icon=meta.get("icon", ""),
            creature_name_ko=meta.get("creature_name_ko", ""),
            creature_emoji=meta.get("creature_emoji", ""),
            creature_description=meta.get("creature_description", ""),
        )

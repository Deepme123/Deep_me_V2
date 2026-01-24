from typing import List

from pydantic import BaseModel, Field, field_validator

from app.desire.core.needs_definitions import NEEDS_METADATA, NeedCode


class NeedCardRequest(BaseModel):
    """User conversation payload for need analysis."""

    conversation_text: str = Field(..., description="Full conversation text to analyze")


class NeedScore(BaseModel):
    code: NeedCode
    label_ko: str
    label_en: str
    score: int = Field(..., ge=0, le=100, description="Score between 0 and 100")
    rank: int = Field(..., ge=1, le=8, description="1=highest priority need, 8=lowest")

    class Config:
        use_enum_values = True


class NeedCardResponse(BaseModel):
    """Eight needs with scores and ranking plus top-4 convenience slice."""

    needs: List[NeedScore]
    top4: List[NeedScore]

    @classmethod
    def from_scores(cls, scores_by_code: dict[str, int]) -> "NeedCardResponse":
        items = []
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

    class Config:
        use_enum_values = True


class NeedSelectionRequest(BaseModel):
    selected_needs: List[NeedCode] = Field(..., min_length=1, description="At least one selected need code")

    @field_validator("selected_needs")
    @classmethod
    def ensure_unique(cls, values: List[NeedCode]) -> List[NeedCode]:
        if len(values) != len(set(values)):
            raise ValueError("Duplicated need codes are not allowed.")
        return values

    class Config:
        use_enum_values = True


class NeedSelectionResponse(BaseModel):
    needs: List[NeedDetail]

    @classmethod
    def from_codes(cls, codes: List[NeedCode]) -> "NeedSelectionResponse":
        needs: List[NeedDetail] = []
        for code in codes:
            meta = NEEDS_METADATA.get(code)
            if not meta:
                continue
            needs.append(
                NeedDetail(
                    code=code,
                    label_ko=meta["label_ko"],
                    label_en=meta["label_en"],
                    description=meta["description"],
                    icon=meta.get("icon", ""),
                )
            )
        return cls(needs=needs)

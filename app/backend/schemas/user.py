from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DeleteMeRequest(BaseModel):
    """탈퇴 사유는 문구 없이 번호(1~5) 목록으로 받는다 — 문구 매핑은 프론트 담당."""

    reason_codes: Optional[List[int]] = Field(default=None)

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: Optional[List[int]]) -> Optional[List[int]]:
        if value is None:
            return None
        for code in value:
            if not 1 <= code <= 5:
                raise ValueError("reason_codes 항목은 1~5 사이여야 합니다.")
        # 중복 제거 + 정렬해서 저장
        return sorted(set(value))

from typing import List

from pydantic import BaseModel, Field, field_validator


class DeleteMeRequest(BaseModel):
    """탈퇴 사유는 문구 없이 번호(1~5) 목록으로 받는다 — 문구 매핑은 프론트 담당.

    UI에서 항상 사유를 선택하게 되어 있으므로 필수값이다 — 누락되면 앱-서버
    간 계약 불일치로 보고 422로 거부한다.
    """

    reason_codes: List[int] = Field(min_length=1)

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: List[int]) -> List[int]:
        for code in value:
            if not 1 <= code <= 5:
                raise ValueError("reason_codes 항목은 1~5 사이여야 합니다.")
        # 중복 제거 + 정렬해서 저장
        return sorted(set(value))

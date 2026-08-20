from typing import Optional

from pydantic import BaseModel, Field


class DeleteMeRequest(BaseModel):
    """탈퇴 사유는 문구 없이 번호(1~5)만 받는다 — 문구 매핑은 프론트 담당."""

    reason_code: Optional[int] = Field(default=None, ge=1, le=5)

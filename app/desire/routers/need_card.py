from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.desire.schemas.need_card import (
    NeedCardRequest,
    NeedCardResponse,
    NeedSelectionRequest,
    NeedSelectionResponse,
)
from app.desire.services.need_analyzer import analyze_needs

router = APIRouter(
    prefix="/need-cards",
    tags=["need-cards"],
)


@router.post("/analyze", response_model=NeedCardResponse)
async def analyze_need_cards(
    payload: NeedCardRequest,
    db: Session = Depends(get_session),
) -> NeedCardResponse:
    return await analyze_needs(payload.conversation_text, payload.session_id, db)


@router.post("/selection", response_model=NeedSelectionResponse)
async def get_selected_need_cards(payload: NeedSelectionRequest) -> NeedSelectionResponse:
    """
    사용자가 선택한 need code 목록을 받아 메인 화면 렌더링에 필요한
    라벨/설명/아이콘 메타데이터를 반환합니다.
    """
    try:
        return NeedSelectionResponse.from_codes(payload.selected_needs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"선택한 욕구를 처리하는 중 오류가 발생했습니다: {exc}")

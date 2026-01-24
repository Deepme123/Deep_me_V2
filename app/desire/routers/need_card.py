from fastapi import APIRouter, HTTPException

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
async def analyze_need_cards(payload: NeedCardRequest) -> NeedCardResponse:
    """
    대화 한 세션(요약 포함)을 받아서
    8개 욕구 점수 + 상위 4개를 반환하는 API.

    요청:
    {
      "conversation_text": "..."
    }

    응답:
    {
      "needs": [...8개...],
      "top4":  [...4개...]
    }
    """
    return await analyze_needs(payload.conversation_text)


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

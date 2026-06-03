from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.backend.dependencies.auth import get_current_user
from app.desire.crud.need_card import get_last_need_card_result_by_user, get_need_card_history_by_user
from app.desire.schemas.need_card import (
    NeedCardHistoryItem,
    NeedCardHistoryResponse,
    NeedCardRequest,
    NeedCardResponse,
    NeedListResponse,
    NeedSelectionRequest,
    NeedSelectionResponse,
)
from app.desire.services.need_analyzer import analyze_needs

router = APIRouter(
    prefix="/need-cards",
    tags=["need-cards"],
)


@router.get("/list", response_model=NeedListResponse)
async def list_needs() -> NeedListResponse:
    return NeedListResponse.all()


@router.post("/analyze", response_model=NeedCardResponse)
async def analyze_need_cards(
    payload: NeedCardRequest,
    db: Session = Depends(get_session),
) -> NeedCardResponse:
    return await analyze_needs(payload.conversation_text, payload.session_id, db)


@router.get("/history", response_model=NeedCardHistoryResponse)
async def get_need_card_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    user_id: str = Depends(get_current_user),
) -> NeedCardHistoryResponse:
    """로그인 유저의 욕구 분석 히스토리 목록을 반환합니다."""
    rows, total = get_need_card_history_by_user(db, UUID(user_id), limit=limit, offset=offset)

    items = []
    for row in rows:
        scores_by_code = {score.code: score.score for score in row.scores}
        card_response = NeedCardResponse.from_scores(scores_by_code)
        items.append(
            NeedCardHistoryItem(
                result_id=row.result_id,
                session_id=row.session_id,
                created_at=row.created_at,
                top4=card_response.top4,
            )
        )

    return NeedCardHistoryResponse(items=items, total=total)


@router.get("/last-selection", response_model=NeedCardResponse)
async def get_last_selection(
    db: Session = Depends(get_session),
    user_id: str = Depends(get_current_user),
) -> NeedCardResponse:
    """로그인 유저의 가장 최근 욕구 분석 결과를 반환합니다."""
    result = get_last_need_card_result_by_user(db, UUID(user_id))
    if result is None:
        raise HTTPException(status_code=404, detail="저장된 욕구 분석 결과가 없습니다.")

    scores_by_code = {score.code: score.score for score in result.scores}
    return NeedCardResponse.from_scores(scores_by_code)


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

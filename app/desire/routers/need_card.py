from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.backend.dependencies.auth import get_current_user
from app.desire.crud.need_card import (
    get_last_need_card_result_by_user,
    get_need_card_history_by_user,
    get_need_card_result_by_session,
    get_last_user_need_selection,
    save_user_need_selection,
)
from app.desire.models.need_card import NeedCardResult
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


def _find_reflection_message(result: Optional[NeedCardResult], code: str) -> str:
    """분석 결과에서 선택된 code에 해당하는 개인화 서술을 찾는다. 없으면 빈 문자열."""
    if result is None:
        return ""
    for score in result.scores:
        if score.code == code:
            return score.reflection_message
    return ""


def _resolve_need_card_result(
    db: Session, user_id: UUID, session_id: Optional[UUID]
) -> Optional[NeedCardResult]:
    """session_id가 있으면 그 세션의 분석 결과를 정확히 찾고, 없거나 못 찾으면 유저의 가장 최근 분석 결과로 폴백한다."""
    if session_id is not None:
        result = get_need_card_result_by_session(db, session_id, user_id)
        if result is not None:
            return result
    return get_last_need_card_result_by_user(db, user_id)


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
        rationales_by_code = {score.code: score.rationale for score in row.scores}
        reflection_messages_by_code = {score.code: score.reflection_message for score in row.scores}
        card_response = NeedCardResponse.from_scores(
            scores_by_code, rationales_by_code, reflection_messages_by_code
        )
        items.append(
            NeedCardHistoryItem(
                result_id=row.result_id,
                session_id=row.session_id,
                created_at=row.created_at,
                top4=card_response.top4,
            )
        )

    return NeedCardHistoryResponse(items=items, total=total)


@router.get("/last-selection", response_model=NeedSelectionResponse)
async def get_last_selection(
    db: Session = Depends(get_session),
    user_id: str = Depends(get_current_user),
) -> NeedSelectionResponse:
    """로그인 유저가 마지막으로 선택한 욕구 하나를 반환합니다."""
    selection = get_last_user_need_selection(db, UUID(user_id))
    if selection is None:
        raise HTTPException(status_code=404, detail="선택한 욕구가 없습니다.")

    code = selection.selected_codes[0]
    result = _resolve_need_card_result(db, UUID(user_id), selection.session_id)
    return NeedSelectionResponse.from_code(code, _find_reflection_message(result, code))


@router.post("/selection", response_model=NeedSelectionResponse)
async def post_selected_need_cards(
    payload: NeedSelectionRequest,
    db: Session = Depends(get_session),
    user_id: str = Depends(get_current_user),
) -> NeedSelectionResponse:
    """사용자가 선택한 욕구를 저장하고 메타데이터를 반환합니다."""
    code = str(payload.selected_need)
    save_user_need_selection(db, UUID(user_id), [code], session_id=payload.session_id)
    try:
        result = _resolve_need_card_result(db, UUID(user_id), payload.session_id)
        return NeedSelectionResponse.from_code(code, _find_reflection_message(result, code))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"선택한 욕구를 처리하는 중 오류가 발생했습니다: {exc}")

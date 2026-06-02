from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.desire.crud.need_card import get_need_card_result_by_session
from app.desire.core.needs_definitions import NEEDS_METADATA, NeedCode
from app.desire.schemas.need_card import (
    NeedCardRequest,
    NeedCardResponse,
    NeedCardResultResponse,
    NeedListResponse,
    NeedScore,
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


@router.get("/results/{session_id}", response_model=NeedCardResultResponse)
async def get_need_card_result(
    session_id: UUID,
    db: Session = Depends(get_session),
) -> NeedCardResultResponse:
    """세션에 저장된 욕구 분석 결과를 조회합니다. 홈 화면에서 선택한 욕구카드 표시에 사용."""
    result = get_need_card_result_by_session(db, session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 세션의 욕구 분석 결과가 없습니다.")

    needs: list[NeedScore] = []
    for score_row in sorted(result.scores, key=lambda s: s.rank):
        code = NeedCode(score_row.code)
        meta = NEEDS_METADATA[code]
        needs.append(
            NeedScore(
                code=code,
                label_ko=meta["label_ko"],
                label_en=meta["label_en"],
                score=score_row.score,
                rank=score_row.rank,
                creature_name_ko=meta.get("creature_name_ko", ""),
                creature_emoji=meta.get("creature_emoji", ""),
                creature_description=meta.get("creature_description", ""),
            )
        )

    return NeedCardResultResponse(
        result_id=result.result_id,
        session_id=result.session_id,
        created_at=result.created_at,
        needs=needs,
        top4=needs[:4],
    )


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

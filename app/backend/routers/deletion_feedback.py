"""탈퇴 사유 집계/export 라우터.

현재 이 프로젝트에는 관리자 인증 체계가 없어서(is_admin 플래그, 별도 토큰
등 없음) 이 라우터는 의도적으로 인증 없이 노출한다 — 운영 배포 전에는
최소한 시크릿 헤더/IP 제한 등으로 접근을 제한해야 한다. 노출 범위를
줄이기 위해 summary는 집계 카운트만, export도 익명 UUID와 사유 코드만
반환하고 이메일/이름 등 식별 정보는 포함하지 않는다.
"""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.backend.models.deletion_feedback import DeletionFeedback
from app.db.session import get_session

router = APIRouter(prefix="/admin/deletion-feedback", tags=["admin"])

# app/backend/schemas/user.py의 DeleteMeRequest 검증 범위(1~5)와 동일하게 유지.
REASON_CODE_RANGE = range(1, 6)


@router.get("/summary")
def get_deletion_feedback_summary(db: Session = Depends(get_session)):
    rows = db.exec(select(DeletionFeedback.reason_codes)).all()

    counts: Counter[int] = Counter()
    for reason_codes in rows:
        counts.update(reason_codes)

    return {
        "total": len(rows),
        "by_reason": {str(code): counts.get(code, 0) for code in REASON_CODE_RANGE},
    }


@router.get("/export")
def export_deletion_feedback(db: Session = Depends(get_session)):
    rows = db.exec(
        select(DeletionFeedback).order_by(DeletionFeedback.created_at.desc())
    ).all()

    return [
        {
            "user_id": str(row.user_id),
            "reason_codes": row.reason_codes,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

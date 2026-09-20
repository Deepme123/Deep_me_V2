"""탈퇴 사유 집계/export 라우터.

민감 데이터(탈퇴 유저 user_id·사유·시각)를 다루므로 `ADMIN_API_SECRET` 헤더
검증(`X-Admin-Secret`)을 거친다. 이 프로젝트에는 별도 관리자 인증 체계(is_admin
플래그, 별도 admin JWT 등)가 없어서 시크릿 헤더로 임시 보호하는 것이며,
`ADMIN_API_SECRET`이 설정되지 않은 환경에서는 라우터 전체를 막는다
(fail-closed) — 시크릿을 비워두는 실수로 무인증 노출되는 것을 막기 위함.
"""

import hmac
import os
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.backend.core.rate_limit import limiter
from app.backend.models.deletion_feedback import DeletionFeedback
from app.backend.schemas.user import VALID_REASON_CODES
from app.db.session import get_session

ADMIN_API_SECRET = os.getenv("ADMIN_API_SECRET", "")


def _require_admin_secret(request: Request) -> None:
    if not ADMIN_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="admin_access_not_configured"
        )

    provided = request.headers.get("X-Admin-Secret", "")
    if not provided or not hmac.compare_digest(provided, ADMIN_API_SECRET):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_admin_secret")


router = APIRouter(
    prefix="/admin/deletion-feedback",
    tags=["admin"],
    dependencies=[Depends(_require_admin_secret)],
)


@router.get("/summary")
@limiter.limit("10/minute")
def get_deletion_feedback_summary(request: Request, db: Session = Depends(get_session)):
    rows = db.exec(select(DeletionFeedback.reason_codes)).all()

    counts: Counter[int] = Counter()
    for reason_codes in rows:
        counts.update(reason_codes)

    return {
        "total": len(rows),
        "by_reason": {str(code): counts.get(code, 0) for code in VALID_REASON_CODES},
    }


@router.get("/export")
@limiter.limit("10/minute")
def export_deletion_feedback(request: Request, db: Session = Depends(get_session)):
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

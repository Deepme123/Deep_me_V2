from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.backend.core.tokens import clear_refresh_cookie
from app.core.auth import get_current_user
from app.backend.models.refresh_token import RefreshToken
from app.backend.models.user import User
from app.backend.services.account_deletion import ACCOUNT_DELETION_GRACE_MINUTES
from app.db.session import get_session


user_router = APIRouter()

@user_router.get("/me/cookie")
def get_me_cookie(user_id: str = Depends(get_current_user)):
    return {"message": "✅ 쿠키 인증 성공", "user_id": user_id}

@user_router.get("/me/bearer")
def get_me_bearer(user_id: str = Depends(get_current_user)):
    return {"message": "✅ 헤더(Bearer) 인증 성공", "user_id": user_id}


@user_router.delete("/me")
def delete_me(
    response: Response,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """회원 탈퇴를 예약한다. 즉시 삭제하지 않고 유예 기간(기본 1시간) 뒤
    백그라운드 스케줄러(`app/backend/core/deletion_scheduler.py`)가 실제
    삭제(`app/backend/services/account_deletion.py`)를 수행한다.

    호출 즉시 리프레시 토큰을 모두 무효화하고 쿠키를 지워 재로그인을 막는다.
    단, 이미 발급된 액세스 토큰은 만료 전까지 계속 유효할 수 있다 — 즉시
    세션 무효화가 필요하면 추후 별도 처리가 필요하다.
    """
    user = db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    if user.deletion_requested_at is None:
        user.deletion_requested_at = datetime.utcnow()
        db.add(user)

    for row in db.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user.user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ):
        row.revoked_at = datetime.utcnow()

    db.commit()

    clear_refresh_cookie(response)
    response.delete_cookie("access_token", path="/")

    scheduled_at = user.deletion_requested_at + timedelta(minutes=ACCOUNT_DELETION_GRACE_MINUTES)
    return {
        "message": "회원 탈퇴가 예약되었습니다.",
        "scheduled_deletion_at": scheduled_at.isoformat(),
    }












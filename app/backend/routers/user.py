from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.backend.core.tokens import clear_refresh_cookie
from app.backend.dependencies.auth import get_current_user
from app.backend.models.user import User
from app.backend.schemas.user import DeleteMeRequest
from app.backend.services.account_deletion import schedule_account_deletion
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
    body: DeleteMeRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """회원 탈퇴를 예약한다. 즉시 삭제하지 않고 유예 기간(기본 5일) 뒤
    백그라운드 스케줄러(`app/backend/core/deletion_scheduler.py`)가 실제
    삭제(`app/backend/services/account_deletion.py`)를 수행한다.

    호출 즉시 리프레시 토큰을 모두 무효화하고 쿠키를 지워 재로그인을 막는다.
    단, 이미 발급된 액세스 토큰은 만료 전까지 계속 유효할 수 있다 — 즉시
    세션 무효화가 필요하면 추후 별도 처리가 필요하다.

    또한 email을 반납 처리하므로, 유예 기간 중 같은 구글 계정으로 재로그인해도
    기존 계정으로는 접근할 수 없고 새 계정으로 생성된다(탈퇴 취소 기능은 의도적으로
    미구현).
    """
    user = db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    scheduled_at = schedule_account_deletion(db, user, body.reason_codes)

    clear_refresh_cookie(response)
    response.delete_cookie("access_token", path="/")

    return {
        "message": "회원 탈퇴가 예약되었습니다.",
        "scheduled_deletion_at": scheduled_at.isoformat(),
    }












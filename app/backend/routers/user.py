from fastapi import APIRouter, Depends, HTTPException, status
from app.backend.dependencies.auth import get_current_user


user_router = APIRouter()

@user_router.get("/me/cookie")
def get_me_cookie(user_id: str = Depends(get_current_user)):
    return {"message": "✅ 쿠키 인증 성공", "user_id": user_id}

@user_router.get("/me/bearer")
def get_me_bearer(user_id: str = Depends(get_current_user)):
    return {"message": "✅ 헤더(Bearer) 인증 성공", "user_id": user_id}


@user_router.delete("/me")
def delete_me(user_id: str = Depends(get_current_user)):
    """회원 탈퇴 껍데기. 실제 삭제 로직은 아직 구현되지 않았다.

    구현 시 삭제 순서(FK RESTRICT 회피 필요):
    1. AnalysisCard, SatisfactionRating (session_id 참조, cascade 미설정)
    2. EmotionSession (EmotionStep/NeedCardResult/NeedCardScore는 CASCADE로 자동 삭제)
    3. Task, RefreshToken (user_id 참조, cascade 미설정)
    4. User (UserNeedSelection은 CASCADE로 자동 삭제)
    또한 로그아웃과 마찬가지로 리프레시 토큰 무효화 및 쿠키 삭제도 필요하다.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="회원 탈퇴 기능은 아직 구현되지 않았습니다.",
    )












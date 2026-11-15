import os
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.backend.core.runtime_env import is_local_runtime
from app.backend.models.user import User


def ensure_web_test_user(db: Session) -> UUID:
    """
    Upsert a deterministic web-test user and return its UUID.
    """
    email = os.getenv("WEB_TEST_USER_EMAIL", "webtest@local")
    name = os.getenv("WEB_TEST_USER_NAME", "Web Test User")

    existing = db.exec(select(User).where(User.email == email)).first()
    if existing:
        return existing.user_id

    user = User(name=name, email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.user_id


def resolve_emotion_user_id(db: Session, current_user: str | UUID | None) -> UUID:
    """
    Resolve the emotion user id based on auth or web-test mode.
    """
    if current_user:
        try:
            return UUID(str(current_user))
        except Exception:
            raise HTTPException(status_code=401, detail="invalid_token")

    # 무인증 우회는 로컬/개발에서만 연다. Render 테스트 서비스도 열지 않는다 —
    # 감정대화 웹테스트 페이지가 Google 로그인으로 토큰을 받아 접속하므로 필요 없고,
    # 열어 두면 누구나 공용 익명 유저로 테스트 DB를 읽고 쓸 수 있다.
    allow_web_test = os.getenv("EMOTION_NO_AUTH_WEB_TEST", "false").lower() == "true"
    if allow_web_test and is_local_runtime():
        return ensure_web_test_user(db)

    raise HTTPException(status_code=401, detail="Authentication required")

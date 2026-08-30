import os
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.backend.models.user import User

# 웹테스트 무인증 우회는 로컬/개발 환경에서만 허용한다.
# APP_ENV를 지정하지 않은 배포 환경(Render 등)은 기본값이 이 화이트리스트에 없으므로
# EMOTION_NO_AUTH_WEB_TEST가 실수로 true로 남아 있어도 우회가 발동하지 않는다.
_WEB_TEST_ALLOWED_ENVS = {"development", "local"}


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

    allow_web_test = os.getenv("EMOTION_NO_AUTH_WEB_TEST", "false").lower() == "true"
    app_env = os.getenv("APP_ENV", "production").lower()
    if allow_web_test and app_env in _WEB_TEST_ALLOWED_ENVS:
        return ensure_web_test_user(db)

    raise HTTPException(status_code=401, detail="Authentication required")

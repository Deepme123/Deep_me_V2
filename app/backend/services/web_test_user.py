import os
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.backend.models.user import User

# 웹테스트 무인증 우회는 로컬/개발 환경에서만 허용한다.
# APP_ENV를 지정하지 않은 배포 환경(Render 등)은 기본값이 이 화이트리스트에 없으므로
# EMOTION_NO_AUTH_WEB_TEST가 실수로 true로 남아 있어도 우회가 발동하지 않는다.
_WEB_TEST_ALLOWED_ENVS = {"development", "local"}

# 단, 웹테스트용 Render 테스트 서비스는 APP_ENV 없이도 허용한다.
# RENDER_SERVICE_NAME은 Render가 서비스마다 자동 주입하며(deep-me-v2 / deep-me-v2-test),
# 운영 서비스(deep-me-v2)는 이 목록에 없으므로 계속 차단된다.
_WEB_TEST_ALLOWED_RENDER_SERVICES = {"deep-me-v2-test"}


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
    render_service = os.getenv("RENDER_SERVICE_NAME", "")
    allowed_runtime = (
        app_env in _WEB_TEST_ALLOWED_ENVS
        or render_service in _WEB_TEST_ALLOWED_RENDER_SERVICES
    )
    if allow_web_test and allowed_runtime:
        return ensure_web_test_user(db)

    raise HTTPException(status_code=401, detail="Authentication required")

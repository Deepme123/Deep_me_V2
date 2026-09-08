import importlib
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

user_router_module = importlib.import_module("app.backend.routers.user")
auth_router_module = importlib.import_module("app.backend.routers.auth")
user_model = importlib.import_module("app.backend.models.user")
emotion_models = importlib.import_module("app.core.models.emotion")
task_model = importlib.import_module("app.backend.models.task")
refresh_token_model = importlib.import_module("app.backend.models.refresh_token")
analyze_models = importlib.import_module("app.analyze.models")
db_session_module = importlib.import_module("app.db.session")
account_deletion = importlib.import_module("app.backend.services.account_deletion")


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite는 FK 제약을 기본으로 강제하지 않아서, 켜두지 않으면 운영
    # PostgreSQL에서만 터지는 FK/CASCADE 문제를 테스트가 놓친다.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    return engine


def _make_user_with_data(db: Session):
    user = user_model.User(name="탈퇴테스트", email=f"{uuid4()}@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)

    session = emotion_models.EmotionSession(user_id=user.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)

    step = emotion_models.EmotionStep(
        session_id=session.session_id,
        step_order=1,
        step_type="normal",
        user_input="비오네",
        gpt_response="그랬구나",
    )
    card = analyze_models.AnalysisCard(session_id=session.session_id, summary="요약")
    rating = analyze_models.SatisfactionRating(session_id=session.session_id, rating=5)
    task = task_model.Task(user_id=user.user_id, title="할 일")
    token = refresh_token_model.RefreshToken(
        jti=str(uuid4()),
        user_id=user.user_id,
        token_hash="hash",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(step)
    db.add(card)
    db.add(rating)
    db.add(task)
    db.add(token)
    db.commit()

    return user, session, rating, step


class TestDeleteAccount:
    def test_removes_user_data_but_preserves_satisfaction_rating(self, engine):
        with Session(engine) as db:
            user, session, rating, step = _make_user_with_data(db)
            user_id = user.user_id
            rating_id = rating.rating_id
            step_id = step.step_id

            account_deletion.delete_account(db, user)

        with Session(engine) as db:
            assert db.get(user_model.User, user_id) is None
            assert db.get(emotion_models.EmotionSession, session.session_id) is None
            assert db.get(emotion_models.EmotionStep, step_id) is None
            assert db.exec(
                select(analyze_models.AnalysisCard).where(
                    analyze_models.AnalysisCard.session_id == session.session_id
                )
            ).first() is None
            assert db.exec(
                select(task_model.Task).where(task_model.Task.user_id == user_id)
            ).first() is None
            assert db.exec(
                select(refresh_token_model.RefreshToken).where(
                    refresh_token_model.RefreshToken.user_id == user_id
                )
            ).first() is None

            preserved = db.get(analyze_models.SatisfactionRating, rating_id)
            assert preserved is not None
            assert preserved.rating == 5
            assert preserved.session_id is None


class TestGracePeriodDefault:
    def test_default_grace_period_is_five_days(self):
        assert account_deletion.ACCOUNT_DELETION_GRACE_MINUTES == 60 * 24 * 5


class TestSweepDueAccountDeletions:
    def test_only_deletes_users_past_grace_period(self, engine, monkeypatch):
        monkeypatch.setattr(account_deletion, "ACCOUNT_DELETION_GRACE_MINUTES", 60)

        with Session(engine) as db:
            due_user = user_model.User(name="유예지남", email=f"{uuid4()}@example.com")
            due_user.deletion_requested_at = datetime.utcnow() - timedelta(minutes=61)
            not_due_user = user_model.User(name="유예남음", email=f"{uuid4()}@example.com")
            not_due_user.deletion_requested_at = datetime.utcnow() - timedelta(minutes=1)
            untouched_user = user_model.User(name="탈퇴안함", email=f"{uuid4()}@example.com")
            db.add(due_user)
            db.add(not_due_user)
            db.add(untouched_user)
            db.commit()
            due_id, not_due_id, untouched_id = (
                due_user.user_id,
                not_due_user.user_id,
                untouched_user.user_id,
            )

        with Session(engine) as db:
            deleted_count = account_deletion.sweep_due_account_deletions(db)

        assert deleted_count == 1
        with Session(engine) as db:
            assert db.get(user_model.User, due_id) is None
            assert db.get(user_model.User, not_due_id) is not None
            assert db.get(user_model.User, untouched_id) is not None

    def test_deletes_user_with_emotion_steps(self, engine, monkeypatch):
        """대화 스텝이 있는 유저도 sweep이 정상 삭제하는지 확인하는 회귀 테스트.

        EmotionSession.steps에 passive_deletes가 없던 시절 ORM이 DB의
        ON DELETE CASCADE 대신 emotionstep.session_id를 NULL로 UPDATE하려
        들어서, 운영에서 sweep이 NotNullViolation으로 5분마다 실패했다.
        """
        monkeypatch.setattr(account_deletion, "ACCOUNT_DELETION_GRACE_MINUTES", 60)

        with Session(engine) as db:
            user, session, _rating, step = _make_user_with_data(db)
            user.deletion_requested_at = datetime.utcnow() - timedelta(minutes=61)
            db.add(user)
            db.commit()
            user_id, session_id, step_id = user.user_id, session.session_id, step.step_id

        with Session(engine) as db:
            deleted_count = account_deletion.sweep_due_account_deletions(db)

        assert deleted_count == 1
        with Session(engine) as db:
            assert db.get(user_model.User, user_id) is None
            assert db.get(emotion_models.EmotionSession, session_id) is None
            assert db.get(emotion_models.EmotionStep, step_id) is None


def _build_client(engine, user_id):
    app = FastAPI()
    app.include_router(user_router_module.user_router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[user_router_module.get_current_user] = lambda: str(user_id)
    app.dependency_overrides[db_session_module.get_session] = _get_db
    return TestClient(app)


class TestDeleteMeEndpoint:
    def test_schedules_deletion_and_revokes_refresh_tokens(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="탈퇴예약", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            token = refresh_token_model.RefreshToken(
                jti=str(uuid4()),
                user_id=user.user_id,
                token_hash="hash",
                expires_at=datetime.utcnow() + timedelta(days=1),
            )
            db.add(token)
            db.commit()
            user_id = user.user_id
            jti = token.jti

        client = _build_client(engine, user_id)

        response = client.delete("/me")

        assert response.status_code == 200
        assert "scheduled_deletion_at" in response.json()

        with Session(engine) as db:
            reloaded = db.get(user_model.User, user_id)
            assert reloaded.deletion_requested_at is not None
            token = db.get(refresh_token_model.RefreshToken, jti)
            assert token.revoked_at is not None

    def test_is_idempotent_and_keeps_original_timestamp(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="중복탈퇴", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)

        first = client.delete("/me")
        first_scheduled_at = first.json()["scheduled_deletion_at"]

        second = client.delete("/me")
        second_scheduled_at = second.json()["scheduled_deletion_at"]

        assert first.status_code == 200
        assert second.status_code == 200
        assert first_scheduled_at == second_scheduled_at

    def test_returns_404_for_missing_user(self, engine):
        client = _build_client(engine, uuid4())

        response = client.delete("/me")

        assert response.status_code == 404

    def test_invalidates_email_so_relogin_creates_new_user(self, engine):
        original_email = f"{uuid4()}@example.com"
        with Session(engine) as db:
            user = user_model.User(name="이메일반납", email=original_email)
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)
        client.delete("/me")

        with Session(engine) as db:
            reloaded = db.get(user_model.User, user_id)
            assert reloaded.email != original_email
            assert reloaded.email == f"deleted+{user_id}@deepme.invalid"

            # 원래 email이 반납됐으니 같은 email로 새 User를 만들 수 있어야 한다
            # (unique 제약에 안 걸림 = auth.py의 _get_or_create_user가 재로그인 시
            # 새 계정을 생성할 수 있다는 뜻).
            new_user = user_model.User(name="재가입", email=original_email)
            db.add(new_user)
            db.commit()

    def test_relogin_with_same_google_email_creates_new_user_via_auth_flow(self, engine):
        """탈퇴 예약 후 같은 구글 계정(email)으로 재로그인하면
        auth.py의 _get_or_create_user가 새 User를 만드는지 확인하는 회귀 테스트."""
        original_email = f"{uuid4()}@example.com"
        with Session(engine) as db:
            user = user_model.User(name="탈퇴후재로그인", email=original_email)
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)
        client.delete("/me")

        with Session(engine) as db:
            new_user = auth_router_module._get_or_create_user(
                db, email=original_email, name="새로가입"
            )
            assert new_user.user_id != user_id
            old_user = db.get(user_model.User, user_id)
            assert old_user.deletion_requested_at is not None

    def test_repeat_call_does_not_change_email_again(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="이메일유지", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)
        client.delete("/me")

        with Session(engine) as db:
            email_after_first_call = db.get(user_model.User, user_id).email

        client.delete("/me")

        with Session(engine) as db:
            assert db.get(user_model.User, user_id).email == email_after_first_call

    def test_stores_reason_codes(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="사유테스트", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)

        response = client.request("DELETE", "/me", json={"reason_codes": [3, 1]})

        assert response.status_code == 200
        with Session(engine) as db:
            reloaded = db.get(user_model.User, user_id)
            assert reloaded.deletion_reasons == [1, 3]

    def test_reason_code_out_of_range_is_rejected(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="범위밖사유", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)

        response = client.request("DELETE", "/me", json={"reason_codes": [6]})

        assert response.status_code == 422
        with Session(engine) as db:
            reloaded = db.get(user_model.User, user_id)
            assert reloaded.deletion_requested_at is None

    def test_repeat_call_does_not_overwrite_existing_reason(self, engine):
        with Session(engine) as db:
            user = user_model.User(name="사유유지", email=f"{uuid4()}@example.com")
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.user_id

        client = _build_client(engine, user_id)

        client.request("DELETE", "/me", json={"reason_codes": [2]})
        client.request("DELETE", "/me", json={"reason_codes": [5]})

        with Session(engine) as db:
            reloaded = db.get(user_model.User, user_id)
            assert reloaded.deletion_reasons == [2]

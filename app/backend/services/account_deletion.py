from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import delete as sa_delete, update as sa_update
from sqlmodel import Session, select

from app.backend.models.refresh_token import RefreshToken
from app.backend.models.task import Task
from app.backend.models.user import User
from app.core.models.emotion import EmotionSession

log = logging.getLogger(__name__)

# 탈퇴 요청 후 실제 삭제까지 대기하는 유예 기간(분). 기본 5일(60*24*5=7200분).
ACCOUNT_DELETION_GRACE_MINUTES = int(os.getenv("ACCOUNT_DELETION_GRACE_MINUTES", "7200"))


def delete_account(db: Session, user: User) -> None:
    """탈퇴 유예 기간이 지난 유저의 데이터를 실제로 삭제한다.

    SatisfactionRating(세션 만족도 평가)은 삭제 범위 밖이라 session_id만
    NULL 처리해 레코드를 보존한다. EmotionStep/NeedCardResult/NeedCardScore/
    UserNeedSelection은 DB의 ON DELETE CASCADE로 자동 정리된다.
    """
    # backend가 analyze의 삭제 대상 모델을 알아야 하는 지점이라 지연 import로
    # 처리 — ws_post_actions.py/reflection_writer.py의 기존 관례와 동일.
    from app.analyze.models import AnalysisCard, SatisfactionRating

    user_session_ids = select(EmotionSession.session_id).where(
        EmotionSession.user_id == user.user_id
    )

    # 아래 문장들은 실행 즉시 DB로 나가므로, 자식 row가 모두 정리된 뒤에야
    # commit 시점의 "DELETE FROM user"가 나간다. 순서를 바꾸면 User를 참조하는
    # EmotionSession/Task/RefreshToken의 FK(ON DELETE CASCADE 없음) 위반이 난다.
    db.exec(
        sa_delete(AnalysisCard).where(AnalysisCard.session_id.in_(user_session_ids)),
        execution_options={"synchronize_session": False},
    )
    db.exec(
        sa_update(SatisfactionRating)
        .where(SatisfactionRating.session_id.in_(user_session_ids))
        .values(session_id=None),
        execution_options={"synchronize_session": False},
    )
    db.exec(
        sa_delete(Task).where(Task.user_id == user.user_id),
        execution_options={"synchronize_session": False},
    )
    db.exec(
        sa_delete(RefreshToken).where(RefreshToken.user_id == user.user_id),
        execution_options={"synchronize_session": False},
    )
    db.exec(
        sa_delete(EmotionSession).where(EmotionSession.user_id == user.user_id),
        execution_options={"synchronize_session": False},
    )

    db.delete(user)
    db.commit()


def sweep_due_account_deletions(db: Session) -> int:
    """유예 기간이 지난 탈퇴 예약 유저를 찾아 실제 삭제를 수행하고, 삭제된 수를 반환한다."""
    cutoff = datetime.utcnow() - timedelta(minutes=ACCOUNT_DELETION_GRACE_MINUTES)
    due_users = db.exec(
        select(User).where(
            User.deletion_requested_at.is_not(None),
            User.deletion_requested_at <= cutoff,
        )
    ).all()

    for user in due_users:
        log.info("account deletion sweep: deleting user_id=%s", user.user_id)
        delete_account(db, user)

    return len(due_users)

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.backend.models.deletion_feedback import DeletionFeedback
from app.backend.models.emotion import EmotionSession, EmotionStep
from app.backend.models.refresh_token import RefreshToken
from app.backend.models.task import Task
from app.backend.models.user import User

log = logging.getLogger(__name__)

# 탈퇴 요청 후 실제 삭제까지 대기하는 유예 기간(분). 기본 5일(60*24*5=7200분).
ACCOUNT_DELETION_GRACE_MINUTES = int(os.getenv("ACCOUNT_DELETION_GRACE_MINUTES", "7200"))


def schedule_account_deletion(db: Session, user: User, reason_codes: list[int]) -> datetime:
    """탈퇴를 예약하고 실제 삭제 예정 시각을 반환한다.

    즉시 삭제하지 않고 deletion_requested_at만 기록한 뒤, 사유를 user row와
    별개인 DeletionFeedback 테이블에 남긴다 — user row는 유예 기간 뒤
    sweep_due_account_deletions()가 삭제하므로, user 컬럼에만 저장하면
    사유가 함께 유실돼 집계가 불가능해진다.

    리프레시 토큰을 모두 무효화해 재로그인을 막고, email을 반납 처리해서
    유예 기간 중 같은 구글 계정으로 재로그인해도 이 탈퇴 예약된 row를
    찾지 못하고 새 User가 생성되도록 한다(탈퇴 취소 기능은 의도적으로 없음).
    """
    if user.deletion_requested_at is None:
        user.deletion_requested_at = datetime.utcnow()
        db.add(DeletionFeedback(user_id=user.user_id, reason_codes=reason_codes))
        user.email = f"deleted+{user.user_id}@deepme.invalid"
        db.add(user)

    for row in db.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user.user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ):
        row.revoked_at = datetime.utcnow()

    db.commit()

    return user.deletion_requested_at + timedelta(minutes=ACCOUNT_DELETION_GRACE_MINUTES)


def delete_account(db: Session, user: User) -> None:
    """탈퇴 유예 기간이 지난 유저의 데이터를 실제로 삭제한다.

    SatisfactionRating(세션 만족도 평가)은 삭제 범위 밖이라 session_id만
    NULL 처리해 레코드를 보존한다. EmotionStep/NeedCardResult/NeedCardScore/
    UserNeedSelection은 DB의 ON DELETE CASCADE에 기대지 않고 여기서 명시적으로
    지운다 — 실제 운영 DB에서 emotionstep_session_id_fkey에 CASCADE가 없는
    스키마 드리프트가 확인돼(마이그레이션 소스에는 CASCADE로 선언돼 있음),
    탈퇴 스윕이 FK 위반으로 계속 실패했었다.
    """
    # backend가 analyze/desire의 삭제 대상 모델을 알아야 하는 지점이라 지연
    # import로 처리 — ws_post_actions.py/reflection_writer.py의 기존 관례와 동일.
    from app.analyze.models import AnalysisCard, SatisfactionRating
    from app.desire.models.need_card import NeedCardResult, NeedCardScore, UserNeedSelection

    session_ids = db.exec(
        select(EmotionSession.session_id).where(EmotionSession.user_id == user.user_id)
    ).all()

    if session_ids:
        for card in db.exec(
            select(AnalysisCard).where(AnalysisCard.session_id.in_(session_ids))
        ):
            db.delete(card)

        for rating in db.exec(
            select(SatisfactionRating).where(SatisfactionRating.session_id.in_(session_ids))
        ):
            rating.session_id = None
            db.add(rating)

        for step in db.exec(
            select(EmotionStep).where(EmotionStep.session_id.in_(session_ids))
        ):
            db.delete(step)

        result_ids = db.exec(
            select(NeedCardResult.result_id).where(NeedCardResult.session_id.in_(session_ids))
        ).all()

        if result_ids:
            for score in db.exec(
                select(NeedCardScore).where(NeedCardScore.result_id.in_(result_ids))
            ):
                db.delete(score)

            for result in db.exec(
                select(NeedCardResult).where(NeedCardResult.result_id.in_(result_ids))
            ):
                db.delete(result)

    for selection in db.exec(
        select(UserNeedSelection).where(UserNeedSelection.user_id == user.user_id)
    ):
        db.delete(selection)

    for task in db.exec(select(Task).where(Task.user_id == user.user_id)):
        db.delete(task)

    for token in db.exec(select(RefreshToken).where(RefreshToken.user_id == user.user_id)):
        db.delete(token)

    for session in db.exec(
        select(EmotionSession).where(EmotionSession.user_id == user.user_id)
    ):
        db.delete(session)

    # User를 참조하는 자식 row(EmotionSession/Task/RefreshToken)의 FK에는
    # ON DELETE CASCADE가 없고 User↔자식 relationship도 없어서, SQLAlchemy가
    # DELETE 순서를 보장해주지 않는다. flush로 자식 삭제를 먼저 내보내
    # "DELETE FROM user"가 앞서 나가 FK 위반이 나는 것을 막는다.
    db.flush()

    db.delete(user)
    db.commit()


def sweep_due_account_deletions(db: Session) -> int:
    """유예 기간이 지난 탈퇴 예약 유저를 찾아 실제 삭제를 수행하고, 삭제된 수를 반환한다.

    유저별 삭제 실패를 격리하지 않으면, 한 명이라도 삭제 중 예외(예상 못한
    FK 제약, 일시적 DB 오류 등)가 나면 그 예외가 그대로 전파돼 이 사이클의
    나머지 대상자 전원이 처리되지 못하고, 다음 사이클에도 같은 유저가 계속
    걸려 전체 삭제 파이프라인이 무기한 막힐 수 있다. 유저별로 격리해서 한
    명의 실패가 다른 유저의 삭제를 막지 않도록 한다.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=ACCOUNT_DELETION_GRACE_MINUTES)
    due_users = db.exec(
        select(User).where(
            User.deletion_requested_at.is_not(None),
            User.deletion_requested_at <= cutoff,
        )
    ).all()

    deleted = 0
    for user in due_users:
        try:
            log.info("account deletion sweep: deleting user_id=%s", user.user_id)
            delete_account(db, user)
            deleted += 1
        except Exception:
            log.exception(
                "account deletion sweep: failed to delete user_id=%s — skipping this cycle",
                user.user_id,
            )
            db.rollback()

    return deleted

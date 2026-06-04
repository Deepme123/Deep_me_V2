from uuid import UUID
from typing import List, Optional

from sqlmodel import Session, select

from app.desire.models.need_card import NeedCardResult, NeedCardScore, UserNeedSelection
from app.desire.schemas.need_card import NeedScore


def get_last_need_card_result_by_user(
    session: Session,
    user_id: UUID,
) -> Optional[NeedCardResult]:
    from app.backend.models.emotion import EmotionSession

    stmt = (
        select(NeedCardResult)
        .join(EmotionSession, NeedCardResult.session_id == EmotionSession.session_id)
        .where(EmotionSession.user_id == user_id)
        .order_by(NeedCardResult.created_at.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def get_need_card_history_by_user(
    session: Session,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[NeedCardResult], int]:
    from app.backend.models.emotion import EmotionSession
    from sqlmodel import func

    base = (
        select(NeedCardResult)
        .join(EmotionSession, NeedCardResult.session_id == EmotionSession.session_id)
        .where(EmotionSession.user_id == user_id)
    )
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        base.order_by(NeedCardResult.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(rows), total


def save_need_card_result(
    session: Session,
    session_id: UUID,
    scores: list[NeedScore],
) -> NeedCardResult:
    result = NeedCardResult(session_id=session_id)
    session.add(result)
    session.flush()

    for item in scores:
        session.add(
            NeedCardScore(
                result_id=result.result_id,
                code=str(item.code),
                score=item.score,
                rank=item.rank,
            )
        )

    session.commit()
    session.refresh(result)
    return result


def save_user_need_selection(
    session: Session,
    user_id: UUID,
    selected_codes: List[str],
) -> UserNeedSelection:
    selection = UserNeedSelection(user_id=user_id, selected_codes=selected_codes)
    session.add(selection)
    session.commit()
    session.refresh(selection)
    return selection


def get_last_user_need_selection(
    session: Session,
    user_id: UUID,
) -> Optional[UserNeedSelection]:
    stmt = (
        select(UserNeedSelection)
        .where(UserNeedSelection.user_id == user_id)
        .order_by(UserNeedSelection.created_at.desc())
        .limit(1)
    )
    return session.exec(stmt).first()

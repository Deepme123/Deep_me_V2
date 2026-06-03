from uuid import UUID
from typing import Optional

from sqlmodel import Session, select

from app.desire.models.need_card import NeedCardResult, NeedCardScore
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

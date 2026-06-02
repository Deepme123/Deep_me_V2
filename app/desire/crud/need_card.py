from uuid import UUID

from sqlmodel import Session, select

from app.desire.models.need_card import NeedCardResult, NeedCardScore
from app.desire.schemas.need_card import NeedScore


def get_need_card_result_by_session(session: Session, session_id: UUID) -> NeedCardResult | None:
    return session.exec(
        select(NeedCardResult)
        .where(NeedCardResult.session_id == session_id)
        .order_by(NeedCardResult.created_at.desc())
    ).first()


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

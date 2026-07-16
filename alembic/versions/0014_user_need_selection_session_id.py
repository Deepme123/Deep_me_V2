"""user_need_selection에 session_id(어느 분석 결과에 대한 선택인지) 컬럼 추가

Revision ID: 0014_user_need_selection_session_id
Revises: 0013_need_card_score_reflection_message
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_user_need_selection_session_id"
down_revision = "0013_need_card_score_reflection_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 클라이언트는 이 필드를 아직 보내지 않으므로 nullable로 추가한다.
    # NULL이면 라우터에서 "유저의 가장 최근 분석 결과"로 폴백한다.
    # SQLite는 기존 테이블에 대한 ADD CONSTRAINT를 지원하지 않아 batch 모드를 사용한다.
    with op.batch_alter_table("user_need_selection") as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_user_need_selection_session_id",
            "emotionsession",
            ["session_id"],
            ["session_id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_user_need_selection_session_id",
            ["session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("user_need_selection") as batch_op:
        batch_op.drop_index("ix_user_need_selection_session_id")
        batch_op.drop_constraint(
            "fk_user_need_selection_session_id", type_="foreignkey"
        )
        batch_op.drop_column("session_id")

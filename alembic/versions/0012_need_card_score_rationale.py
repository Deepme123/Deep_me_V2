"""need_card_score에 rationale(근거 설명) 컬럼 추가

Revision ID: 0012_need_card_score_rationale
Revises: 0011_satisfaction_rating
Create Date: 2026-07-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0012_need_card_score_rationale"
down_revision = "0011_satisfaction_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "need_card_score",
        sa.Column(
            "rationale",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    # 신규 행은 애플리케이션이 값을 채우므로 server_default는 기존 행 백필용으로만 사용.
    op.alter_column("need_card_score", "rationale", server_default=None)


def downgrade() -> None:
    op.drop_column("need_card_score", "rationale")

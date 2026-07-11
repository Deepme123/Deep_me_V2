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
    # server_default=""로 기존 행을 백필한다. SQLite는 ALTER COLUMN DROP DEFAULT를
    # 지원하지 않아 server_default를 이후 제거하지 않고 그대로 둔다 (빈 문자열 기본값은 무해).
    op.add_column(
        "need_card_score",
        sa.Column(
            "rationale",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("need_card_score", "rationale")

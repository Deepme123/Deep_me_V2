"""need_card_score에 reflection_message(선택 시점 개인화 서술) 컬럼 추가

Revision ID: 0013_need_card_score_reflection_message
Revises: 0012_need_card_score_rationale
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_need_card_score_reflection_message"
down_revision = "0012_need_card_score_rationale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default=""로 기존 행을 백필한다. SQLite는 ALTER COLUMN DROP DEFAULT를
    # 지원하지 않아 server_default를 이후 제거하지 않고 그대로 둔다 (빈 문자열 기본값은 무해).
    op.add_column(
        "need_card_score",
        sa.Column(
            "reflection_message",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("need_card_score", "reflection_message")

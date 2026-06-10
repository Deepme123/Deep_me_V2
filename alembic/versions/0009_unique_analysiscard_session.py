"""analysiscard.session_id 유니크 제약 추가

Revision ID: 0009_unique_analysiscard_session
Revises: 0008_rename_emotioncard_to_analysiscard
Create Date: 2026-06-10
"""
from alembic import op

revision = "0009_unique_analysiscard_session"
down_revision = "0008_rename_emotioncard_to_analysiscard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("analysiscard") as batch_op:
        batch_op.create_unique_constraint(
            "uq_analysiscard_session_id",
            ["session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("analysiscard") as batch_op:
        batch_op.drop_constraint("uq_analysiscard_session_id", type_="unique")

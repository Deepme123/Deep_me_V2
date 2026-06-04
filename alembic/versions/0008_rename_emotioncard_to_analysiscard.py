"""rename emotioncard table to analysiscard

Revision ID: 0008_rename_emotioncard_to_analysiscard
Revises: 0007_user_need_selection
Create Date: 2026-06-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_rename_emotioncard_to_analysiscard"
down_revision = "0007_user_need_selection"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("emotioncard", "analysiscard")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            "ALTER INDEX IF EXISTS ix_emotioncard_session_id "
            "RENAME TO ix_analysiscard_session_id"
        ))


def downgrade():
    op.rename_table("analysiscard", "emotioncard")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            "ALTER INDEX IF EXISTS ix_analysiscard_session_id "
            "RENAME TO ix_emotioncard_session_id"
        ))

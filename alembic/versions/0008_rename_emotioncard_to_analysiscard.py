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
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # alembic_version.version_num은 기본 VARCHAR(32)로 생성되는데
        # 이 리비전 ID(39자)가 그보다 길어서 버전 기록 단계에서
        # StringDataRightTruncation으로 실패하고 트랜잭션 전체가 롤백되는 문제가 있었음.
        # 같은 트랜잭션 안에서 먼저 넓혀줘야 함.
        bind.execute(sa.text(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
        ))
    op.rename_table("emotioncard", "analysiscard")
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

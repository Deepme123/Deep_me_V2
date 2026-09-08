"""탈퇴 유예 스윕 쿼리용 user.deletion_requested_at 인덱스 추가

Revision ID: 0019_deletion_requested_at_index
Revises: 0018_deletion_reason_multi
Create Date: 2026-09-08
"""
from alembic import op

revision = "0019_deletion_requested_at_index"
down_revision = "0018_deletion_reason_multi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_deletion_requested_at", "user", ["deletion_requested_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_user_deletion_requested_at", table_name="user")

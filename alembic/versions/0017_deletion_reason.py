"""회원 탈퇴 사유 코드 저장: user.deletion_reason(1~5, nullable) 추가

Revision ID: 0017_deletion_reason
Revises: 0016_account_deletion
Create Date: 2026-08-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_deletion_reason"
down_revision = "0016_account_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("deletion_reason", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("deletion_reason")

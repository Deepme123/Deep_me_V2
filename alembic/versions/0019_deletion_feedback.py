"""탈퇴 사유 집계용 deletionfeedback 테이블 추가, user.deletion_reasons 제거

user 테이블 컬럼에만 사유를 저장하면 유예 기간(기본 5일) 뒤 sweep이 user row를
지울 때 사유도 함께 사라져 집계가 불가능해진다. 별도 테이블로 분리해 user row
삭제와 무관하게 남도록 한다. 아직 sweep되지 않은 유저의 기존 deletion_reasons는
새 테이블로 이관한 뒤 컬럼을 drop한다.

Revision ID: 0019_deletion_feedback
Revises: 0018_deletion_reason_multi
Create Date: 2026-09-13
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "0019_deletion_feedback"
down_revision = "0018_deletion_reason_multi"
branch_labels = None
depends_on = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "deletionfeedback",
        sa.Column("feedback_id", _uuid_type(), nullable=False),
        sa.Column("user_id", _uuid_type(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id"),
    )
    op.create_index("ix_deletionfeedback_user_id", "deletionfeedback", ["user_id"])
    op.create_index("ix_deletionfeedback_created_at", "deletionfeedback", ["created_at"])

    deletionfeedback = table(
        "deletionfeedback",
        column("feedback_id"),
        column("user_id"),
        column("reason_codes"),
        column("created_at"),
    )
    user_table = table(
        "user",
        column("user_id"),
        column("deletion_reasons"),
        column("deletion_requested_at"),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            user_table.c.user_id,
            user_table.c.deletion_reasons,
            user_table.c.deletion_requested_at,
        ).where(user_table.c.deletion_reasons.is_not(None))
    ).fetchall()
    if rows:
        op.bulk_insert(
            deletionfeedback,
            [
                {
                    "feedback_id": uuid.uuid4(),
                    "user_id": row.user_id,
                    "reason_codes": row.deletion_reasons,
                    "created_at": row.deletion_requested_at,
                }
                for row in rows
            ],
        )

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("deletion_reasons")


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("deletion_reasons", sa.JSON(), nullable=True))

    op.drop_index("ix_deletionfeedback_created_at", table_name="deletionfeedback")
    op.drop_index("ix_deletionfeedback_user_id", table_name="deletionfeedback")
    op.drop_table("deletionfeedback")

"""회원 탈퇴 사유 복수 선택 지원: user.deletion_reason(Integer) -> deletion_reasons(JSON 배열)

Revision ID: 0018_deletion_reason_multi
Revises: 0017_deletion_reason
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_deletion_reason_multi"
down_revision = "0017_deletion_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE "user" RENAME COLUMN deletion_reason TO deletion_reasons
            """
        )
        op.execute(
            """
            ALTER TABLE "user"
            ALTER COLUMN deletion_reasons TYPE JSON
            USING (
                CASE
                    WHEN deletion_reasons IS NULL THEN NULL
                    ELSE to_json(ARRAY[deletion_reasons]::int[])
                END
            )
            """
        )
    else:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(sa.Column("deletion_reasons", sa.JSON(), nullable=True))
        op.execute(
            """
            UPDATE "user" SET deletion_reasons = json_array(deletion_reason)
            WHERE deletion_reason IS NOT NULL
            """
        )
        with op.batch_alter_table("user") as batch_op:
            batch_op.drop_column("deletion_reason")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE "user"
            ALTER COLUMN deletion_reasons TYPE INTEGER
            USING (
                CASE
                    WHEN deletion_reasons IS NULL THEN NULL
                    ELSE (deletion_reasons->>0)::integer
                END
            )
            """
        )
        op.execute(
            """
            ALTER TABLE "user" RENAME COLUMN deletion_reasons TO deletion_reason
            """
        )
    else:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(sa.Column("deletion_reason", sa.Integer(), nullable=True))
        op.execute(
            """
            UPDATE "user" SET deletion_reason = json_extract(deletion_reasons, '$[0]')
            WHERE deletion_reasons IS NOT NULL
            """
        )
        with op.batch_alter_table("user") as batch_op:
            batch_op.drop_column("deletion_reasons")

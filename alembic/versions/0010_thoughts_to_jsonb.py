"""analysiscard.thoughts column String to JSONB (감정별 생각 그룹 구조로 변경)

Revision ID: 0010_thoughts_to_jsonb
Revises: 0009_unique_analysiscard_session
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_thoughts_to_jsonb"
down_revision = "0009_unique_analysiscard_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            ALTER TABLE analysiscard
            ALTER COLUMN thoughts TYPE JSONB
            USING NULL
        """)
    else:
        with op.batch_alter_table("analysiscard") as batch_op:
            batch_op.alter_column(
                "thoughts",
                type_=sa.JSON(),
                existing_type=sa.String(),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            ALTER TABLE analysiscard
            ALTER COLUMN thoughts TYPE VARCHAR
            USING NULL
        """)
    else:
        with op.batch_alter_table("analysiscard") as batch_op:
            batch_op.alter_column(
                "thoughts",
                type_=sa.String(),
                existing_type=sa.JSON(),
                existing_nullable=True,
            )

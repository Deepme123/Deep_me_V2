"""physical_reactions column String to JSONB

Revision ID: 0003_physical_reactions_to_jsonb
Revises: 0002_add_emotioncard
Create Date: 2026-05-03 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_physical_reactions_to_jsonb"
down_revision = "0002_add_emotioncard"
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            ALTER TABLE emotioncard
            ALTER COLUMN physical_reactions TYPE JSONB
            USING CASE
                WHEN physical_reactions IS NULL THEN NULL
                ELSE to_jsonb(ARRAY[physical_reactions])
            END
        """)
    else:
        with op.batch_alter_table("emotioncard") as batch_op:
            batch_op.alter_column(
                "physical_reactions",
                type_=sa.JSON(),
                existing_type=sa.String(),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            ALTER TABLE emotioncard
            ALTER COLUMN physical_reactions TYPE VARCHAR
            USING CASE
                WHEN physical_reactions IS NULL THEN NULL
                ELSE physical_reactions->>0
            END
        """)
    else:
        with op.batch_alter_table("emotioncard") as batch_op:
            batch_op.alter_column(
                "physical_reactions",
                type_=sa.String(),
                existing_type=sa.JSON(),
                existing_nullable=True,
            )

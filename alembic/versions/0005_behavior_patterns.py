"""add behavior_patterns JSONB column to emotioncard

Revision ID: 0005_behavior_patterns
Revises: 0004_add_needcard_tables
Create Date: 2026-05-05 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_behavior_patterns"
down_revision = "0004_add_needcard_tables"
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.add_column(
        "emotioncard",
        sa.Column("behavior_patterns", _json_type(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("emotioncard", "behavior_patterns")

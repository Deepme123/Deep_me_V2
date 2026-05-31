"""add situation_steps JSONB column to emotioncard

Revision ID: 0006_situation_steps
Revises: 0005_behavior_patterns
Create Date: 2026-05-16 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_situation_steps"
down_revision = "0005_behavior_patterns"
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
        sa.Column("situation_steps", _json_type(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("emotioncard", "situation_steps")

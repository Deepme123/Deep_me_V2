"""add emotioncard table

Revision ID: 0002_add_emotioncard
Revises: 0001_base_schema
Create Date: 2026-03-23 00:00:01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_add_emotioncard"
down_revision = "0001_base_schema"
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()

    op.create_table(
        "emotioncard",
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("core_emotions", json_type, nullable=True),
        sa.Column("situation", sa.String(), nullable=True),
        sa.Column("emotion", sa.String(), nullable=True),
        sa.Column("thoughts", sa.String(), nullable=True),
        sa.Column("physical_reactions", sa.String(), nullable=True),
        sa.Column("behaviors", sa.String(), nullable=True),
        sa.Column("coping_actions", json_type, nullable=True),
        sa.Column("risk_flag", sa.Boolean(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=True),
        sa.Column("tags", json_type, nullable=True),
        sa.Column("insight", sa.String(), nullable=True),
        sa.Column("exportable", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["emotionsession.session_id"]),
        sa.PrimaryKeyConstraint("card_id"),
    )
    op.create_index("ix_emotioncard_session_id", "emotioncard", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_emotioncard_session_id", table_name="emotioncard")
    op.drop_table("emotioncard")

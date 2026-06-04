"""add user_need_selection table

Revision ID: 0007_user_need_selection
Revises: 0006_situation_steps
Create Date: 2026-06-04 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_user_need_selection"
down_revision = "0006_situation_steps"
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "user_need_selection",
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("selected_codes", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("selection_id"),
    )
    op.create_index("ix_user_need_selection_user_id", "user_need_selection", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_need_selection_user_id", table_name="user_need_selection")
    op.drop_table("user_need_selection")

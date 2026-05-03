"""add need_card_result and need_card_score tables

Revision ID: 0004_add_needcard_tables
Revises: 0003_physical_reactions_to_jsonb
Create Date: 2026-05-03 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0004_add_needcard_tables"
down_revision = "0003_physical_reactions_to_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "need_card_result",
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["emotionsession.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index("ix_need_card_result_session_id", "need_card_result", ["session_id"], unique=False)

    op.create_table(
        "need_card_score",
        sa.Column("score_id", sa.Uuid(), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["result_id"], ["need_card_result.result_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("score_id"),
    )
    op.create_index("ix_need_card_score_result_id", "need_card_score", ["result_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_need_card_score_result_id", table_name="need_card_score")
    op.drop_table("need_card_score")

    op.drop_index("ix_need_card_result_session_id", table_name="need_card_result")
    op.drop_table("need_card_result")

"""create base schema tables

Revision ID: 0001_base_schema
Revises:
Create Date: 2026-03-23 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "emotionsession",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("emotion_label", sa.String(), nullable=True),
        sa.Column("topic", sa.String(), nullable=True),
        sa.Column("trigger_summary", sa.String(), nullable=True),
        sa.Column("insight_summary", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "task",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )

    op.create_table(
        "refreshtoken",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("replaced_by", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"]),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("ix_refreshtoken_user_id", "refreshtoken", ["user_id"], unique=False)

    op.create_table(
        "emotionstep",
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("user_input", sa.String(), nullable=False),
        sa.Column("gpt_response", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("insight_tag", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["emotionsession.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("step_id"),
        sa.UniqueConstraint("session_id", "step_order", name="uq_emotionstep_session_order"),
    )
    op.create_index("ix_emotionstep_session_id", "emotionstep", ["session_id"], unique=False)
    op.create_index(
        "ix_emotionstep_session_order",
        "emotionstep",
        ["session_id", "step_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_emotionstep_session_order", table_name="emotionstep")
    op.drop_index("ix_emotionstep_session_id", table_name="emotionstep")
    op.drop_table("emotionstep")

    op.drop_index("ix_refreshtoken_user_id", table_name="refreshtoken")
    op.drop_table("refreshtoken")

    op.drop_table("task")
    op.drop_table("emotionsession")

    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")

"""satisfactionrating 테이블 추가

Revision ID: 0011_satisfaction_rating
Revises: 0010_thoughts_to_jsonb
Create Date: 2026-07-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_satisfaction_rating"
down_revision = "0010_thoughts_to_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "satisfactionrating",
        sa.Column("rating_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("emotionsession.session_id"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_satisfactionrating_session_id"),
    )
    op.create_index(
        "ix_satisfactionrating_session_id",
        "satisfactionrating",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_satisfactionrating_session_id", table_name="satisfactionrating")
    op.drop_table("satisfactionrating")

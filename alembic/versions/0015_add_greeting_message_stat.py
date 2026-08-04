"""세션 오픈 인사 문구(app/backend/resources/greeting_messages.txt) 선택 횟수 카운터 테이블 추가

Revision ID: 0015_add_greeting_message_stat
Revises: 0014_user_need_selection_session_id
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0015_add_greeting_message_stat"
down_revision = "0014_user_need_selection_session_id"
branch_labels = None
depends_on = None

# app/backend/resources/greeting_messages.txt 문구 개수와 일치해야 한다.
GREETING_MESSAGE_COUNT = 10


def upgrade() -> None:
    op.create_table(
        "greetingmessagestat",
        sa.Column("message_index", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
    )
    table = sa.table(
        "greetingmessagestat",
        sa.column("message_index", sa.Integer()),
        sa.column("selected_count", sa.Integer()),
    )
    op.bulk_insert(
        table,
        [{"message_index": i, "selected_count": 0} for i in range(GREETING_MESSAGE_COUNT)],
    )


def downgrade() -> None:
    op.drop_table("greetingmessagestat")

"""세션 오픈 인사 문구(app/backend/resources/greeting_messages.txt) 선택 횟수 카운터 테이블 추가

원래 0015(0014 → 0015 → 0016)였지만, 운영(main)에는 0015 없이 0014 → 0016 →
... → 0019가 먼저 적용됐다. 이미 head인 DB는 체인 중간에 끼어든 리비전을 실행하지
않으므로 체인 끝으로 옮겼다. 0015로 이미 테이블이 만들어진 DB(테스트 서버 등)도
이 리비전을 다시 지나가게 되므로, 테이블이 있으면 생성을 건너뛴다.

Revision ID: 0020_add_greeting_message_stat
Revises: 0019_deletion_feedback
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_add_greeting_message_stat"
down_revision = "0019_deletion_feedback"
branch_labels = None
depends_on = None

# app/backend/resources/greeting_messages.txt 문구 개수와 일치해야 한다.
GREETING_MESSAGE_COUNT = 10


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("greetingmessagestat"):
        return

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

"""emotionsession.flow_state — 데모 1.2 대화 흐름 상태(JSON) 저장 칸

판단기 신호로 정한 대화 단계(자유/제안함/단계, 마무리 위치, 나온·물어본 항목)를
세션마다 저장해 매 턴/재접속 시 다시 불러온다.

Revision ID: 0022_emotionsession_flow_state
Revises: 0021_add_prompt_revision
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_emotionsession_flow_state"
down_revision = "0021_add_prompt_revision"
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    op.add_column("emotionsession", sa.Column("flow_state", _json_type(), nullable=True))


def downgrade() -> None:
    op.drop_column("emotionsession", "flow_state")

"""테스트 서버 프롬프트 연구용 promptrevision 테이블 추가

C-1(2026-05-09)에서 제거했던 /prompts 수정 API를 테스트 서버 한정으로 복원하면서,
파일 덮어쓰기 대신 DB에 수정 이력을 남긴다 (Render 재배포 시 파일 변경이 사라지므로).

Revision ID: 0021_add_prompt_revision
Revises: 0020_add_greeting_message_stat
Create Date: 2026-10-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_add_prompt_revision"
down_revision = "0020_add_greeting_message_stat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promptrevision",
        sa.Column("revision_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_type", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("revision_id"),
    )
    op.create_index("ix_promptrevision_prompt_type", "promptrevision", ["prompt_type"])


def downgrade() -> None:
    op.drop_index("ix_promptrevision_prompt_type", table_name="promptrevision")
    op.drop_table("promptrevision")

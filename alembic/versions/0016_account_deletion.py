"""회원 탈퇴(지연 삭제) 지원: user.deletion_requested_at 추가,
satisfactionrating.session_id를 nullable + ON DELETE SET NULL로 변경

Revision ID: 0016_account_deletion
Revises: 0014_user_need_selection_session_id
Create Date: 2026-08-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0016_account_deletion"
down_revision = "0014_user_need_selection_session_id"
branch_labels = None
depends_on = None

# satisfactionrating.session_id의 FK는 0011에서 이름 없이 생성돼, DB가 자동
# 명명한다 — postgres는 실제 생성 경로에 따라 이름이 달라질 수 있고(반드시
# "<table>_<column>_fkey"가 아닐 수 있다), sqlite는 애초에 이름을 저장하지
# 않는다(테스트가 sqlite로 head까지 마이그레이션을 돈다). postgres에서는
# inspector로 실제 이름을 조회해 드롭하고, sqlite는 naming_convention으로
# reflect 시 결정적인 이름을 부여해 배치 모드가 대상을 식별하게 한다.
_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}
_REFLECTED_FK_NAME = "fk_satisfactionrating_session_id_emotionsession"


def _existing_session_id_fk_name(bind) -> str:
    for fk in sa.inspect(bind).get_foreign_keys("satisfactionrating"):
        if fk["constrained_columns"] == ["session_id"]:
            return fk["name"]
    raise RuntimeError("satisfactionrating.session_id의 FK 제약을 찾을 수 없습니다.")


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("deletion_requested_at", sa.DateTime(), nullable=True)
        )

    # SatisfactionRating은 탈퇴 시 보존 대상이라, 세션이 삭제돼도 레코드가
    # 남도록 session_id를 nullable로 바꾸고 ON DELETE SET NULL로 재생성한다.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        existing_fk_name = _existing_session_id_fk_name(bind)
        with op.batch_alter_table("satisfactionrating") as batch_op:
            batch_op.drop_constraint(existing_fk_name, type_="foreignkey")
            batch_op.alter_column("session_id", nullable=True)
            batch_op.create_foreign_key(
                "satisfactionrating_session_id_fkey",
                "emotionsession",
                ["session_id"],
                ["session_id"],
                ondelete="SET NULL",
            )
    else:
        with op.batch_alter_table(
            "satisfactionrating", naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_constraint(_REFLECTED_FK_NAME, type_="foreignkey")
            batch_op.alter_column("session_id", nullable=True)
            batch_op.create_foreign_key(
                "satisfactionrating_session_id_fkey",
                "emotionsession",
                ["session_id"],
                ["session_id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.batch_alter_table("satisfactionrating") as batch_op:
            batch_op.drop_constraint(
                "satisfactionrating_session_id_fkey", type_="foreignkey"
            )
            batch_op.alter_column("session_id", nullable=False)
            batch_op.create_foreign_key(
                "satisfactionrating_session_id_fkey",
                "emotionsession",
                ["session_id"],
                ["session_id"],
            )
    else:
        with op.batch_alter_table(
            "satisfactionrating", naming_convention=_NAMING_CONVENTION
        ) as batch_op:
            batch_op.drop_constraint(
                "satisfactionrating_session_id_fkey", type_="foreignkey"
            )
            batch_op.alter_column("session_id", nullable=False)
            batch_op.create_foreign_key(
                _REFLECTED_FK_NAME,
                "emotionsession",
                ["session_id"],
                ["session_id"],
            )

    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("deletion_requested_at")

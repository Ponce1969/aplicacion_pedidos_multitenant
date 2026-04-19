"""004_add_password_reset_token

Revision ID: 0b6aa527a9d3
Revises: afff0db3b2a2
Create Date: 2026-04-19 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0b6aa527a9d3"
down_revision: Union[str, None] = "afff0db3b2a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=100), nullable=False),
        sa.Column("expiracion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_password_reset_tokens_token"), "password_reset_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_password_reset_tokens_usuario_id"), "password_reset_tokens", ["usuario_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_password_reset_tokens_usuario_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

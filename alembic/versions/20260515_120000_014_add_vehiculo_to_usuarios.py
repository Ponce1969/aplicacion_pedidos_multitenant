"""Add vehiculo, celular and ci columns to usuarios table

Revision ID: 014
Revises: 013
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "vehiculo",
            sa.String(100),
            nullable=True,
            server_default=None,
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "celular",
            sa.String(30),
            nullable=True,
            server_default=None,
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "ci",
            sa.String(20),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "ci")
    op.drop_column("usuarios", "celular")
    op.drop_column("usuarios", "vehiculo")
"""Make hora_entrega optional (nullable)

Revision ID: 009
Revises: 008
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make hora_entrega nullable
    op.alter_column("pedidos", "hora_entrega",
                    existing_type=sa.String(10),
                    nullable=True)


def downgrade() -> None:
    # Revert hora_entrega to NOT NULL (set empty string for nulls first)
    op.execute("UPDATE pedidos SET hora_entrega = '' WHERE hora_entrega IS NULL")
    op.alter_column("pedidos", "hora_entrega",
                    existing_type=sa.String(10),
                    nullable=False)
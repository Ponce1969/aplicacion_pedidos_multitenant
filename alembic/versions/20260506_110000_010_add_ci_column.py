"""Add CI (cedula de identidad) column to clientes and pedidos

Revision ID: 010
Revises: 009
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ci column to clientes (nullable — existing records won't have it)
    op.add_column("clientes", sa.Column("ci", sa.String(20), nullable=True))
    # Add ci column to pedidos (nullable — legacy records won't have it)
    op.add_column("pedidos", sa.Column("ci", sa.String(20), nullable=True))
    # Add unique constraint for CI per empresa
    op.create_unique_constraint("uq_cliente_empresa_ci", "clientes", ["empresa_id", "ci"])


def downgrade() -> None:
    op.drop_constraint("uq_cliente_empresa_ci", "clientes", type_="unique")
    op.drop_column("pedidos", "ci")
    op.drop_column("clientes", "ci")
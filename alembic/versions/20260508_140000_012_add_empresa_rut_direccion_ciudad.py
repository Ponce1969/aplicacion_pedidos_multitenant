"""Add rut, direccion, ciudad to empresas table

Revision ID: 012
Revises: 011
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empresas", sa.Column("rut", sa.String(20), nullable=True))
    op.add_column("empresas", sa.Column("direccion", sa.String(200), nullable=True))
    op.add_column("empresas", sa.Column("ciudad", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("empresas", "ciudad")
    op.drop_column("empresas", "direccion")
    op.drop_column("empresas", "rut")
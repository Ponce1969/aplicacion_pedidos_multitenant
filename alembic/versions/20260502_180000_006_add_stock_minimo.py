"""006_add_stock_minimo

Revision ID: 006_add_stock_minimo
Revises: 005_add_empresa_branding_fields
Create Date: 2026-05-02 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_add_stock_minimo'
down_revision: Union[str, Sequence[str], None] = '005_add_empresa_branding_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stock_minimo field to productos for low-stock alerts."""
    op.add_column('productos',
        sa.Column('stock_minimo', sa.Numeric(precision=12, scale=2), nullable=True)
    )


def downgrade() -> None:
    """Remove stock_minimo field."""
    op.drop_column('productos', 'stock_minimo')

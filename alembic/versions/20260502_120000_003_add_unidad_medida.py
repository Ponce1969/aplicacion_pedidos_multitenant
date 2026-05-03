"""003_add_unidad_medida

Revision ID: 003_add_unidad_medida
Revises: 002_add_senia_and_estado_pago
Create Date: 2026-05-02 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_unidad_medida'
down_revision: Union[str, Sequence[str], None] = '002_add_senia_and_estado_pago'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unidad_medida field to productos with default 'unidad'."""
    
    # Agregar campo unidad_medida con server_default para datos existentes
    op.add_column('productos',
        sa.Column('unidad_medida', sa.String(length=20),
                  nullable=False, server_default='unidad')
    )


def downgrade() -> None:
    """Remove unidad_medida field."""
    op.drop_column('productos', 'unidad_medida')

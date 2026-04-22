"""002_add_senia_and_estado_pago

Revision ID: 002_add_senia_and_estado_pago
Revises: 001_initial_schema
Create Date: 2026-04-21 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '002_add_senia_and_estado_pago'
down_revision: Union[str, Sequence[str], None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add senia (deposit) and estado_pago (payment status) fields to pedidos."""
    
    # Agregar campo senia (seña/adelanto)
    op.add_column('pedidos', 
        sa.Column('senia', sa.Numeric(precision=12, scale=2), 
                  nullable=True, server_default='0')
    )
    
    # Agregar campo estado_pago
    op.add_column('pedidos',
        sa.Column('estado_pago', sa.String(length=20),
                  nullable=False, server_default='pendiente')
    )
    
    # Crear índice para búsquedas por estado de pago
    op.create_index('idx_pedido_estado_pago', 'pedidos', ['estado_pago'], unique=False)


def downgrade() -> None:
    """Remove senia and estado_pago fields."""
    op.drop_index('idx_pedido_estado_pago', table_name='pedidos')
    op.drop_column('pedidos', 'estado_pago')
    op.drop_column('pedidos', 'senia')

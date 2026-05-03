"""008_add_cuenta_corriente

Revision ID: 008_add_cuenta_corriente
Revises: 007_add_cliente_direcciones
Create Date: 2026-05-02 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '008_add_cuenta_corriente'
down_revision: Union[str, Sequence[str], None] = '007_add_cliente_direcciones'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cuenta corriente fields to clientes and create pagos table."""
    
    # ==================== 1. CLIENTES: saldo y límite ====================
    op.add_column('clientes',
        sa.Column('saldo_pendiente', sa.Numeric(precision=12, scale=2),
                  nullable=False, server_default='0')
    )
    op.add_column('clientes',
        sa.Column('limite_credito', sa.Numeric(precision=12, scale=2), nullable=True)
    )
    op.create_index('idx_cliente_saldo', 'clientes', ['saldo_pendiente'], unique=False)
    
    # ==================== 2. PAGOS: crear tabla ====================
    op.create_table('pagos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('pedido_id', sa.Integer(), nullable=True),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('metodo_pago', sa.String(length=30),
                  nullable=False, server_default='efectivo'),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('registrado_por', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id']),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuarios.id']),
    )
    op.create_index('idx_pago_cliente', 'pagos', ['cliente_id'], unique=False)
    op.create_index('idx_pago_empresa', 'pagos', ['empresa_id'], unique=False)
    op.create_index('idx_pago_pedido', 'pagos', ['pedido_id'], unique=False)
    op.create_index('ix_pagos_cliente_id', 'pagos', ['cliente_id'], unique=False)
    op.create_index('ix_pagos_empresa_id', 'pagos', ['empresa_id'], unique=False)


def downgrade() -> None:
    """Remove cuenta corriente."""
    op.drop_table('pagos')
    op.drop_index('idx_cliente_saldo', table_name='clientes')
    op.drop_column('clientes', 'limite_credito')
    op.drop_column('clientes', 'saldo_pendiente')

"""004_add_rol_repartidor_and_entrega_eventos

Revision ID: 004_add_rol_repartidor_and_entrega_eventos
Revises: 003_add_unidad_medida
Create Date: 2026-05-02 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '004_add_rol_repartidor_and_entrega_eventos'
down_revision: Union[str, Sequence[str], None] = '003_add_unidad_medida'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rol to usuarios, repartidor_id to pedidos, create entrega_eventos."""
    
    # ==================== 1. USUARIOS: agregar rol ====================
    op.add_column('usuarios',
        sa.Column('rol', sa.String(length=20),
                  nullable=False, server_default='operador')
    )
    
    # Migrar datos: is_admin=True → rol='admin'
    op.execute("UPDATE usuarios SET rol = 'admin' WHERE is_admin = 1")
    op.execute("UPDATE usuarios SET rol = 'admin' WHERE is_admin = true")
    
    # Crear índice para búsquedas por rol
    op.create_index('idx_usuario_rol', 'usuarios', ['rol'], unique=False)
    
    # ==================== 2. PEDIDOS: agregar repartidor_id ====================
    op.add_column('pedidos',
        sa.Column('repartidor_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_pedido_repartidor', 'pedidos', 'usuarios', 
        ['repartidor_id'], ['id']
    )
    op.create_index('idx_pedido_repartidor', 'pedidos', ['repartidor_id'], unique=False)
    
    # ==================== 3. ENTREGA_EVENTOS: crear tabla ====================
    op.create_table('entrega_eventos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pedido_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('estado_anterior', sa.String(length=30), nullable=True),
        sa.Column('estado_nuevo', sa.String(length=30), nullable=False),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
    )
    op.create_index('idx_evento_pedido', 'entrega_eventos', ['pedido_id'], unique=False)
    op.create_index('idx_evento_empresa', 'entrega_eventos', ['empresa_id'], unique=False)
    op.create_index('ix_entrega_eventos_pedido_id', 'entrega_eventos', ['pedido_id'], unique=False)
    op.create_index('ix_entrega_eventos_empresa_id', 'entrega_eventos', ['empresa_id'], unique=False)


def downgrade() -> None:
    """Remove rol, repartidor_id, and entrega_eventos."""
    op.drop_table('entrega_eventos')
    op.drop_index('idx_pedido_repartidor', table_name='pedidos')
    op.drop_constraint('fk_pedido_repartidor', 'pedidos', type_='foreignkey')
    op.drop_column('pedidos', 'repartidor_id')
    op.drop_index('idx_usuario_rol', table_name='usuarios')
    op.drop_column('usuarios', 'rol')

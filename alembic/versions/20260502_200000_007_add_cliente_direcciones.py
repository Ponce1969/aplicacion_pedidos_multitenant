"""007_add_cliente_direcciones

Revision ID: 007_add_cliente_direcciones
Revises: 006_add_stock_minimo
Create Date: 2026-05-02 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '007_add_cliente_direcciones'
down_revision: Union[str, Sequence[str], None] = '006_add_stock_minimo'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cliente_direcciones table for multiple delivery addresses per client."""
    op.create_table('cliente_direcciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('descripcion', sa.String(length=100), nullable=False),
        sa.Column('direccion', sa.Text(), nullable=False),
        sa.Column('es_principal', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
    )
    op.create_index('idx_dir_cliente', 'cliente_direcciones', ['cliente_id'], unique=False)
    op.create_index('idx_dir_empresa', 'cliente_direcciones', ['empresa_id'], unique=False)
    op.create_index('ix_cliente_direcciones_cliente_id', 'cliente_direcciones', ['cliente_id'], unique=False)
    op.create_index('ix_cliente_direcciones_empresa_id', 'cliente_direcciones', ['empresa_id'], unique=False)

    # Migrar direcciones existentes de clientes como dirección principal
    op.execute("""
        INSERT INTO cliente_direcciones (cliente_id, empresa_id, descripcion, direccion, es_principal)
        SELECT id, empresa_id, 'Principal', direccion, true
        FROM clientes
        WHERE direccion IS NOT NULL AND direccion != ''
    """)


def downgrade() -> None:
    """Drop cliente_direcciones table."""
    op.drop_table('cliente_direcciones')

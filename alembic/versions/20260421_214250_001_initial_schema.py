"""001_initial_schema

Revision ID: 001_initial_schema
Create Date: 2026-04-21 21:42:50

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create complete schema — all tables in dependency order."""
    
    # ==================== 1. EMPRESAS (root table) ====================
    op.create_table('empresas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('rubro', sa.String(length=100), nullable=True),
        sa.Column('moneda', sa.String(length=10), server_default='UYU', nullable=False),
        sa.Column('zona_horaria', sa.String(length=50), server_default='America/Montevideo', nullable=False),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_empresa_slug', 'empresas', ['slug'], unique=False)
    
    # ==================== 2. USUARIOS ====================
    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellido', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('ultimo_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.UniqueConstraint('empresa_id', 'email', name='uq_usuario_empresa_email')
    )
    op.create_index('idx_usuario_email', 'usuarios', ['email'], unique=False)
    op.create_index('ix_usuarios_empresa_id', 'usuarios', ['empresa_id'], unique=False)
    
    # ==================== 3. CLIENTES ====================
    op.create_table('clientes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellido', sa.String(length=100), nullable=False),
        sa.Column('celular', sa.String(length=20), nullable=False),
        sa.Column('direccion', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.UniqueConstraint('empresa_id', 'celular', name='uq_cliente_empresa_celular')
    )
    op.create_index('idx_cliente_celular', 'clientes', ['celular'], unique=False)
    op.create_index('ix_clientes_celular', 'clientes', ['celular'], unique=False)
    op.create_index('ix_clientes_empresa_id', 'clientes', ['empresa_id'], unique=False)
    
    # ==================== 4. PRODUCTOS ====================
    op.create_table('productos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=True),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('precio_base', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('stock', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('categoria', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.UniqueConstraint('empresa_id', 'sku', name='uq_producto_empresa_sku')
    )
    op.create_index('idx_producto_nombre', 'productos', ['nombre'], unique=False)
    op.create_index('ix_productos_empresa_id', 'productos', ['empresa_id'], unique=False)
    
    # ==================== 5. PEDIDOS ====================
    op.create_table('pedidos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellido', sa.String(length=100), nullable=False),
        sa.Column('celular', sa.String(length=20), nullable=False),
        sa.Column('direccion', sa.String(length=200), nullable=False),
        sa.Column('hora_entrega', sa.String(length=10), nullable=False),
        sa.Column('pedido_detalle', sa.Text(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('impuestos', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('estado', sa.String(length=20), server_default='pendiente', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('fecha_entrega', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], )
    )
    op.create_index('idx_celular', 'pedidos', ['celular'], unique=False)
    op.create_index('idx_apellido', 'pedidos', ['apellido'], unique=False)
    op.create_index('idx_fecha_creacion', 'pedidos', ['fecha_creacion'], unique=False)
    op.create_index('idx_usuario_pedidos', 'pedidos', ['usuario_id'], unique=False)
    op.create_index('idx_pedido_cliente', 'pedidos', ['cliente_id'], unique=False)
    op.create_index('idx_pedido_empresa', 'pedidos', ['empresa_id'], unique=False)
    op.create_index('ix_pedidos_cliente_id', 'pedidos', ['cliente_id'], unique=False)
    op.create_index('ix_pedidos_empresa_id', 'pedidos', ['empresa_id'], unique=False)
    
    # ==================== 6. PEDIDO_ITEMS ====================
    op.create_table('pedido_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pedido_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=True),
        sa.Column('descripcion', sa.String(length=300), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('precio_unitario', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id'], )
    )
    op.create_index('idx_item_pedido', 'pedido_items', ['pedido_id'], unique=False)
    op.create_index('ix_pedido_items_pedido_id', 'pedido_items', ['pedido_id'], unique=False)
    op.create_index('ix_pedido_items_producto_id', 'pedido_items', ['producto_id'], unique=False)
    
    # ==================== 7. CONFIGURACION ====================
    op.create_table('configuracion',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('clave', sa.String(length=100), nullable=False),
        sa.Column('valor', sa.String(length=500), nullable=False),
        sa.Column('descripcion', sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
        sa.UniqueConstraint('empresa_id', 'clave', name='uq_config_empresa_clave')
    )
    op.create_index('idx_config_clave', 'configuracion', ['clave'], unique=False)
    op.create_index('ix_configuracion_empresa_id', 'configuracion', ['empresa_id'], unique=False)
    
    # ==================== 8. TOKEN_BLACKLIST ====================
    op.create_table('token_blacklist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('expiracion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # ==================== 9. PASSWORD_RESET_TOKENS ====================
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=100), nullable=False),
        sa.Column('expiracion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usado', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_password_reset_tokens_token', 'password_reset_tokens', ['token'], unique=False)
    op.create_index('ix_password_reset_tokens_usuario_id', 'password_reset_tokens', ['usuario_id'], unique=False)
    
    # ==================== SEED DATA ====================
    # Insertar empresa default
    op.execute("INSERT INTO empresas (nombre, slug, rubro) VALUES ('Mi Empresa', 'default', 'General')")
    
    # Insertar usuario admin (password: TPgpOe4SMt82c6XJ - Argon2)
    op.execute("""
        INSERT INTO usuarios (empresa_id, email, nombre, apellido, password_hash, is_admin) 
        VALUES (1, 'admin@barraca.com', 'Admin', 'Sistema', 
                '$argon2id$v=19$m=65536,t=2,p=1$3FvLOWcMoVSq9f5/bw0BgA$lfcpX4oIKxcXNfbzH86272znJk6dZZti6g+Bp+bhc0g', 
                true)
    """)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('password_reset_tokens')
    op.drop_table('token_blacklist')
    op.drop_table('configuracion')
    op.drop_table('pedido_items')
    op.drop_table('pedidos')
    op.drop_table('productos')
    op.drop_table('clientes')
    op.drop_table('usuarios')
    op.drop_table('empresas')

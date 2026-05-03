"""005_add_empresa_branding_fields

Revision ID: 005_add_empresa_branding_fields
Revises: 004_add_rol_repartidor_and_entrega_eventos
Create Date: 2026-05-02 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_add_empresa_branding_fields'
down_revision: Union[str, Sequence[str], None] = '004_add_rol_repartidor_and_entrega_eventos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add branding fields to empresas for multi-tenant email customization."""
    
    op.add_column('empresas',
        sa.Column('email_contacto', sa.String(length=100), nullable=True)
    )
    op.add_column('empresas',
        sa.Column('telefono_contacto', sa.String(length=50), nullable=True)
    )
    op.add_column('empresas',
        sa.Column('color_primario', sa.String(length=7),
                  nullable=False, server_default='#3b82f6')
    )


def downgrade() -> None:
    """Remove branding fields."""
    op.drop_column('empresas', 'color_primario')
    op.drop_column('empresas', 'telefono_contacto')
    op.drop_column('empresas', 'email_contacto')

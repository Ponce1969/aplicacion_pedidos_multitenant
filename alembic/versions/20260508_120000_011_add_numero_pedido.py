"""Add numero_pedido column with unique constraint per empresa

Revision ID: 011
Revises: 010
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add numero_pedido column (nullable first for backfill)
    op.add_column("pedidos", sa.Column("numero_pedido", sa.Integer(), nullable=True))

    # Backfill: assign sequential numero_pedido per empresa based on fecha_creacion
    op.execute("""
        WITH ranked AS (
            SELECT id, empresa_id,
                   ROW_NUMBER() OVER (PARTITION BY empresa_id ORDER BY fecha_creacion, id) AS rn
            FROM pedidos
        )
        UPDATE pedidos SET numero_pedido = ranked.rn
        FROM ranked
        WHERE pedidos.id = ranked.id
    """)

    # Make non-nullable after backfill
    op.alter_column("pedidos", "numero_pedido", nullable=False)

    # Add unique constraint: (empresa_id, numero_pedido)
    op.create_unique_constraint("uq_pedido_empresa_numero", "pedidos", ["empresa_id", "numero_pedido"])


def downgrade() -> None:
    op.drop_constraint("uq_pedido_empresa_numero", "pedidos", type_="unique")
    op.drop_column("pedidos", "numero_pedido")
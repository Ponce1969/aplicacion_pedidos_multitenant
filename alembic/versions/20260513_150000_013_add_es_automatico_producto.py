"""add es_automatico to productos, unique index nombre+empresa CI, dedup

Revision ID: 013
Revises: 012
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PASO 1: Agregar columna es_automatico (default False = manual)
    # Productos existentes son manuales (cargados por admin), solo los JIT seran True
    op.add_column(
        "productos",
        sa.Column(
            "es_automatico",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # PASO 2: Normalizar nombres existentes — INITCAP ≈ .title(), BTRIM ≈ .strip()
    # Esto previene duplicados case-insensitive antes de crear el índice único.
    op.execute("""
        UPDATE productos
        SET nombre = INITCAP(BTRIM(nombre))
        WHERE nombre <> INITCAP(BTRIM(nombre))
    """)

    # PASO 3: Deduplicar — re-asignar pedido_items al sobreviviente y eliminar duplicados.
    # El sobreviviente es el producto con mayor id por grupo (empresa_id, nombre normalizado).
    # Esto es seguro: si no hay duplicados, los DELETEs no afectan ninguna fila.

    # 3a: Re-asignar pedido_items del producto duplicado (menor id) al sobreviviente (mayor id)
    op.execute("""
        UPDATE pedido_items
        SET producto_id = sub.survivor_id
        FROM (
            SELECT pi.producto_id AS old_id,
                   MAX(p.id) OVER (
                       PARTITION BY p.empresa_id, LOWER(BTRIM(p.nombre))
                   ) AS survivor_id
            FROM pedido_items pi
            JOIN productos p ON p.id = pi.producto_id
        ) AS sub
        WHERE pedido_items.producto_id = sub.old_id
          AND sub.old_id <> sub.survivor_id
    """)

    # 3b: Eliminar productos duplicados (queda el de mayor id)
    op.execute("""
        DELETE FROM productos p1
        USING productos p2
        WHERE p1.empresa_id = p2.empresa_id
          AND LOWER(BTRIM(p1.nombre)) = LOWER(BTRIM(p2.nombre))
          AND p1.id < p2.id
    """)

    # PASO 4: Crear índice único funcional case-insensitive
    # Este índice previene duplicados como "Arena" vs "arena" vs " Arena "
    op.execute("""
        CREATE UNIQUE INDEX uq_productos_nombre_empresa_ci
        ON productos (empresa_id, LOWER(BTRIM(nombre)))
    """)


def downgrade() -> None:
    # Revertir en orden inverso
    op.execute("DROP INDEX IF EXISTS uq_productos_nombre_empresa_ci")
    op.drop_column("productos", "es_automatico")
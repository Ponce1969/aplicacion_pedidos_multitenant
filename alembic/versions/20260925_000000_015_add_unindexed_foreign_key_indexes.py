"""Add unindexed foreign key indexes for entrega_eventos and pagos

Revision ID: 015
Revises: 014
Create Date: 2026-09-25
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        with op.get_context().autocommit_block():
            op.create_index(
                "idx_evento_usuario",
                "entrega_eventos",
                ["usuario_id"],
                unique=False,
                postgresql_concurrently=True,
                if_not_exists=True,
            )
            op.create_index(
                "idx_pago_registrado_por",
                "pagos",
                ["registrado_por"],
                unique=False,
                postgresql_concurrently=True,
                if_not_exists=True,
            )
    else:
        op.create_index(
            "idx_evento_usuario",
            "entrega_eventos",
            ["usuario_id"],
            unique=False,
        )
        op.create_index(
            "idx_pago_registrado_por",
            "pagos",
            ["registrado_por"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        with op.get_context().autocommit_block():
            op.drop_index(
                "idx_pago_registrado_por",
                table_name="pagos",
                postgresql_concurrently=True,
                if_exists=True,
            )
            op.drop_index(
                "idx_evento_usuario",
                table_name="entrega_eventos",
                postgresql_concurrently=True,
                if_exists=True,
            )
    else:
        op.drop_index(
            "idx_pago_registrado_por",
            table_name="pagos",
        )
        op.drop_index(
            "idx_evento_usuario",
            table_name="entrega_eventos",
        )

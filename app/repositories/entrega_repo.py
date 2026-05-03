"""Repositorio para EntregaEvento — registro de cambios de estado."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntregaEvento


async def create(
    db: AsyncSession,
    pedido_id: int,
    usuario_id: int,
    empresa_id: int,
    estado_anterior: str | None,
    estado_nuevo: str,
    nota: str | None = None,
) -> EntregaEvento:
    """Crea un evento de cambio de estado de entrega."""
    evento = EntregaEvento(
        pedido_id=pedido_id,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        nota=nota,
    )
    db.add(evento)
    await db.commit()
    await db.refresh(evento)
    return evento


async def get_by_pedido(
    db: AsyncSession,
    pedido_id: int,
) -> list[EntregaEvento]:
    """Obtiene todos los eventos de un pedido, ordenados cronológicamente."""
    query = (
        select(EntregaEvento)
        .where(EntregaEvento.pedido_id == pedido_id)
        .order_by(EntregaEvento.created_at.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_pedidos_asignados_hoy(
    db: AsyncSession,
    repartidor_id: int,
    empresa_id: int,
    fecha: date | None = None,
) -> list[EntregaEvento]:
    """Obtiene los eventos del día para los pedidos asignados a un repartidor."""
    from app.models import Pedido

    # Buscar pedidos asignados al repartidor
    query = (
        select(Pedido)
        .where(
            Pedido.repartidor_id == repartidor_id,
            Pedido.empresa_id == empresa_id,
            Pedido.estado.notin_(["cancelado", "entregado"]),
        )
        .order_by(Pedido.fecha_entrega.asc().nulls_last())
    )
    result = await db.execute(query)
    return list(result.scalars().all())

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pedido


async def get_by_id(db: AsyncSession, pedido_id: int, empresa_id: int) -> Pedido | None:
    result = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id, Pedido.empresa_id == empresa_id)
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, pedido: Pedido) -> Pedido:
    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return pedido


async def search_by_celular_or_apellido(
    db: AsyncSession,
    termino: str,
    empresa_id: int,
) -> list[Pedido]:
    from sqlalchemy import func

    query = (
        select(Pedido)
        .where(
            Pedido.empresa_id == empresa_id,
            (Pedido.celular.contains(termino))
            | (Pedido.ci.contains(termino))
            | (Pedido.apellido.ilike(f"%{termino}%"))
            | (Pedido.nombre.ilike(f"%{termino}%"))
            | (func.concat(Pedido.nombre, " ", Pedido.apellido).ilike(f"%{termino}%")),
        )
        .order_by(Pedido.fecha_creacion.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_by_month(db: AsyncSession, primer_dia_mes: date, empresa_id: int) -> list[Pedido]:
    query = (
        select(Pedido)
        .where(Pedido.empresa_id == empresa_id, Pedido.fecha_creacion >= primer_dia_mes)
        .order_by(Pedido.fecha_creacion.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_pending_by_empresa(
    db: AsyncSession,
    empresa_id: int,
    fecha: date | None = None,
) -> list[Pedido]:
    """Obtiene pedidos pendientes, opcionalmente filtrados por fecha de entrega."""
    query = select(Pedido).where(
        Pedido.empresa_id == empresa_id,
        Pedido.estado == "pendiente",
    )
    if fecha is not None:
        query = query.where(func.date(Pedido.fecha_entrega) == fecha)

    query = query.order_by(Pedido.fecha_entrega.asc().nulls_last(), Pedido.hora_entrega)
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_pedido(db: AsyncSession, pedido_id: int, empresa_id: int) -> bool:
    """Elimina un pedido por ID. Devuelve True si existía y pertenece a la empresa."""
    pedido = await get_by_id(db, pedido_id, empresa_id)
    if pedido is None:
        return False
    await db.delete(pedido)
    await db.commit()
    return True


async def get_asignados_by_repartidor(
    db: AsyncSession,
    repartidor_id: int,
    empresa_id: int,
) -> list[Pedido]:
    """Obtiene pedidos asignados a un repartidor (no cancelados ni entregados)."""
    query = (
        select(Pedido)
        .where(
            Pedido.repartidor_id == repartidor_id,
            Pedido.empresa_id == empresa_id,
            Pedido.estado.notin_(["cancelado", "entregado"]),
        )
        .order_by(Pedido.fecha_entrega.asc().nulls_last(), Pedido.hora_entrega)
    )
    result = await db.execute(query)
    return list(result.scalars().all())

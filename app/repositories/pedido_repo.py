from datetime import date

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Pedido, PedidoItem, Producto


async def get_by_id(db: AsyncSession, pedido_id: int, empresa_id: int) -> Pedido | None:
    result = await db.execute(
        select(Pedido).where(Pedido.id == pedido_id, Pedido.empresa_id == empresa_id)
    )
    return result.scalar_one_or_none()


async def get_by_id_with_items(
    db: AsyncSession, pedido_id: int, empresa_id: int
) -> Pedido | None:
    """Obtiene un pedido con items y productos precargados (evita N+1)."""
    result = await db.execute(
        select(Pedido)
        .where(Pedido.id == pedido_id, Pedido.empresa_id == empresa_id)
        .options(
            selectinload(Pedido.items).selectinload(PedidoItem.producto),
        )
    )
    return result.scalar_one_or_none()


async def next_numero_pedido(db: AsyncSession, empresa_id: int) -> int:
    """Devuelve el siguiente numero_pedido disponible para una empresa.

    Usa MAX+1 con locking para evitar condiciones de carrera en multi-tenant.
    Si no hay pedidos, retorna 1.
    """
    result = await db.execute(
        select(func.coalesce(func.max(Pedido.numero_pedido), 0) + 1).where(
            Pedido.empresa_id == empresa_id
        )
    )
    return result.scalar_one()


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
    from sqlalchemy import func as sa_func

    # Normalizar: colapsar múltiples espacios a uno solo
    termino = " ".join(termino.split())

    query = (
        select(Pedido)
        .where(
            Pedido.empresa_id == empresa_id,
            (Pedido.celular.contains(termino))
            | (Pedido.ci.contains(termino))
            | (Pedido.apellido.ilike(f"%{termino}%"))
            | (Pedido.nombre.ilike(f"%{termino}%"))
            | (sa_func.concat(Pedido.nombre, " ", Pedido.apellido).ilike(f"%{termino}%")),
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


async def list_all_for_export(db: AsyncSession, empresa_id: int) -> list[Pedido]:
    """Obtiene todos los pedidos de una empresa para exportación CSV.

    Usa selectinload para traer items y repartidor en 1 query cada uno,
    evitando N+1 lazy loading por cada pedido.
    """
    query = (
        select(Pedido)
        .where(Pedido.empresa_id == empresa_id)
        .options(
            selectinload(Pedido.items),
            selectinload(Pedido.repartidor),
        )
        .order_by(Pedido.numero_pedido.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_top_productos_mes(
    db: AsyncSession, empresa_id: int, limit: int = 5
) -> list[tuple[str, float]]:
    """Top N productos más vendidos del mes. Una sola query SQL con GROUP BY.

    Retorna lista de (descripcion, total_vendido) ordenada de mayor a menor.
    Filtra pedidos cancelados.
    """
    from datetime import UTC, datetime

    hoy = datetime.now(UTC).date()
    primer_dia_mes = hoy.replace(day=1)

    query = (
        select(
            PedidoItem.descripcion,
            func.sum(PedidoItem.cantidad).label("total_vendido"),
        )
        .join(Pedido, PedidoItem.pedido_id == Pedido.id)
        .where(
            Pedido.empresa_id == empresa_id,
            Pedido.fecha_creacion >= primer_dia_mes,
            Pedido.estado != "cancelado",
        )
        .group_by(PedidoItem.descripcion)
        .order_by(func.sum(PedidoItem.cantidad).desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return [(row.descripcion, float(row.total_vendido)) for row in result.all()]

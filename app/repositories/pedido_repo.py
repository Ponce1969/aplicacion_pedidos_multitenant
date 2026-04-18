from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pedido


async def get_by_id(db: AsyncSession, pedido_id: int) -> Pedido | None:
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, pedido: Pedido) -> Pedido:
    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return pedido


async def search_by_celular_or_apellido(db: AsyncSession, termino: str) -> list[Pedido]:
    query = (
        select(Pedido)
        .where((Pedido.celular.contains(termino)) | (Pedido.apellido.ilike(f"%{termino}%")))
        .order_by(Pedido.fecha_creacion.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_by_month(db: AsyncSession, primer_dia_mes: date) -> list[Pedido]:
    query = (
        select(Pedido)
        .where(Pedido.fecha_creacion >= primer_dia_mes)
        .order_by(Pedido.fecha_creacion.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())

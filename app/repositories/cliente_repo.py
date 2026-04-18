from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cliente


async def get_by_id(db: AsyncSession, cliente_id: int) -> Cliente | None:
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    return result.scalar_one_or_none()


async def get_by_celular(db: AsyncSession, celular: str) -> Cliente | None:
    result = await db.execute(select(Cliente).where(Cliente.celular == celular))
    return result.scalar_one_or_none()


async def search(db: AsyncSession, termino: str) -> list[Cliente]:
    query = (
        select(Cliente)
        .where(
            (Cliente.celular.contains(termino))
            | (Cliente.apellido.ilike(f"%{termino}%"))
            | (Cliente.nombre.ilike(f"%{termino}%")),
        )
        .order_by(Cliente.apellido)
        .limit(20)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create(db: AsyncSession, cliente: Cliente) -> Cliente:
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


async def create_or_get_by_celular(db: AsyncSession, cliente: Cliente) -> Cliente:
    existing = await get_by_celular(db, cliente.celular)
    if existing is not None:
        return existing
    return await create(db, cliente)

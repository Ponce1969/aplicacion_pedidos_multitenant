from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Producto


async def get_by_id(db: AsyncSession, producto_id: int) -> Producto | None:
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    return result.scalar_one_or_none()


async def search(db: AsyncSession, termino: str) -> list[Producto]:
    query = (
        select(Producto)
        .where(
            Producto.is_active == True,  # noqa: E712
            (Producto.nombre.ilike(f"%{termino}%"))
            | (Producto.sku.ilike(f"%{termino}%")),
        )
        .order_by(Producto.nombre)
        .limit(20)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_active(db: AsyncSession) -> list[Producto]:
    query = (
        select(Producto)
        .where(Producto.is_active == True)  # noqa: E712
        .order_by(Producto.nombre)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create(db: AsyncSession, producto: Producto) -> Producto:
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Producto


class InsufficientStockError(Exception):
    """Error cuando no hay stock suficiente para un producto."""

    def __init__(self, producto_nombre: str, stock_disponible: Decimal, cantidad_solicitada: Decimal) -> None:
        self.producto_nombre = producto_nombre
        self.stock_disponible = stock_disponible
        self.cantidad_solicitada = cantidad_solicitada
        super().__init__(
            f"Stock insuficiente para '{producto_nombre}': "
            f"disponible {stock_disponible}, solicitado {cantidad_solicitada}"
        )


async def get_by_id(db: AsyncSession, producto_id: int, empresa_id: int) -> Producto | None:
    result = await db.execute(
        select(Producto).where(Producto.id == producto_id, Producto.empresa_id == empresa_id)
    )
    return result.scalar_one_or_none()


async def search(db: AsyncSession, termino: str, empresa_id: int) -> list[Producto]:
    query = (
        select(Producto)
        .where(
            Producto.empresa_id == empresa_id,
            Producto.is_active == True,  # noqa: E712
            (Producto.nombre.ilike(f"%{termino}%"))
            | (Producto.sku.ilike(f"%{termino}%")),
        )
        .order_by(Producto.nombre)
        .limit(20)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_active(db: AsyncSession, empresa_id: int) -> list[Producto]:
    query = (
        select(Producto)
        .where(Producto.empresa_id == empresa_id, Producto.is_active == True)  # noqa: E712
        .order_by(Producto.nombre)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create(db: AsyncSession, producto: Producto) -> Producto:
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto


async def update_stock(
    db: AsyncSession, producto_id: int, empresa_id: int, nuevo_stock: Decimal,
) -> Producto | None:
    """Actualiza el stock de un producto. Retorna el producto actualizado o None si no existe."""
    producto = await get_by_id(db, producto_id, empresa_id)
    if producto is None:
        return None
    producto.stock = nuevo_stock
    await db.commit()
    await db.refresh(producto)
    return producto


async def get_stock_bajo(db: AsyncSession, empresa_id: int) -> list[Producto]:
    """Obtiene productos con stock por debajo del mínimo configurado.
    
    Un producto tiene stock bajo cuando:
    - stock_minimo NO es None (tiene alerta configurada)
    - stock NO es None (tiene control de stock)
    - stock <= stock_minimo
    """
    query = (
        select(Producto)
        .where(
            Producto.empresa_id == empresa_id,
            Producto.is_active == True,  # noqa: E712
            Producto.stock_minimo.isnot(None),
            Producto.stock.isnot(None),
            Producto.stock <= Producto.stock_minimo,
        )
        .order_by(Producto.stock.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_stock_bajo(db: AsyncSession, empresa_id: int) -> int:
    """Cuenta productos con stock bajo (para el badge del dashboard)."""
    from sqlalchemy import func

    query = (
        select(func.count())
        .select_from(Producto)
        .where(
            Producto.empresa_id == empresa_id,
            Producto.is_active == True,  # noqa: E712
            Producto.stock_minimo.isnot(None),
            Producto.stock.isnot(None),
            Producto.stock <= Producto.stock_minimo,
        )
    )
    result = await db.execute(query)
    count: int = result.scalar() or 0
    return count


async def list_all(db: AsyncSession, empresa_id: int, include_inactive: bool = False) -> list[Producto]:
    """Lista todos los productos de una empresa. Include_inactive incluye los desactivados."""
    query = select(Producto).where(Producto.empresa_id == empresa_id)
    if not include_inactive:
        query = query.where(Producto.is_active == True)  # noqa: E712
    query = query.order_by(Producto.is_active.desc(), Producto.nombre)
    result = await db.execute(query)
    return list(result.scalars().all())


async def deactivate(db: AsyncSession, producto_id: int, empresa_id: int) -> Producto | None:
    """Desactiva un producto (soft delete). Retorna None si no existe."""
    producto = await get_by_id(db, producto_id, empresa_id)
    if producto is None:
        return None
    producto.is_active = False
    await db.commit()
    await db.refresh(producto)
    return producto


async def activate(db: AsyncSession, producto_id: int, empresa_id: int) -> Producto | None:
    """Reactiva un producto desactivado."""
    producto = await get_by_id(db, producto_id, empresa_id)
    if producto is None:
        return None
    producto.is_active = True
    await db.commit()
    await db.refresh(producto)
    return producto

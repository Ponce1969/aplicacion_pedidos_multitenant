from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pedido, PedidoItem
from app.repositories import pedido_repo


async def crear_pedido(db: AsyncSession, pedido: Pedido) -> Pedido:
    """Crea un pedido nuevo en la BD."""
    return await pedido_repo.create(db, pedido)


async def crear_pedido_con_items(
    db: AsyncSession, pedido: Pedido, items: list[dict],
) -> Pedido:
    """Crea un pedido con sus líneas de items. Calcula el total automáticamente."""
    subtotal = 0.0
    for item_data in items:
        cantidad = float(item_data.get("cantidad", 1.0))
        precio = float(item_data.get("precio_unitario", 0.0))
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        item = PedidoItem(
            descripcion=item_data["descripcion"],
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal,
            producto_id=item_data.get("producto_id"),
        )
        pedido.items.append(item)

    pedido.subtotal = subtotal
    pedido.total = subtotal + float(pedido.impuestos or 0.0)
    return await pedido_repo.create(db, pedido)


async def buscar_pedidos(db: AsyncSession, termino: str, empresa_id: int) -> list[Pedido]:
    """Busca pedidos por celular o apellido."""
    return await pedido_repo.search_by_celular_or_apellido(db, termino, empresa_id)


async def get_pedido(db: AsyncSession, pedido_id: int) -> Pedido | None:
    """Obtiene un pedido por ID."""
    return await pedido_repo.get_by_id(db, pedido_id)


def calcular_top_productos(pedidos: list[Pedido]) -> list[tuple[str, float]]:
    """Parsea pedido_detalle (legacy) para obtener productos más vendidos."""
    productos_vendidos: dict[str, float] = {}
    for pedido in pedidos:
        try:
            lineas: list[str] = pedido.pedido_detalle.split("\n")
            for linea in lineas:
                if "-" in linea:
                    partes: list[str] = linea.split("-", 1)
                    nombre_prod: str = partes[0].strip()
                    try:
                        cantidad_str = partes[1].strip().replace("kg", "").replace("unidad", "").strip()
                        cantidad: float = float(cantidad_str)
                    except (ValueError, IndexError):
                        cantidad = 1.0
                    productos_vendidos[nombre_prod] = productos_vendidos.get(nombre_prod, 0.0) + cantidad
        except (AttributeError, ValueError):
            pass

    return sorted(productos_vendidos.items(), key=lambda x: x[1], reverse=True)[:5]


def calcular_kpis_mes(pedidos: list[Pedido]) -> tuple[float, int]:
    """Calcula total_ventas y cantidad_pedidos de una lista de pedidos."""
    total_ventas = sum(float(pedido.total) for pedido in pedidos)
    cantidad = len(pedidos)
    return total_ventas, cantidad


async def get_pedidos_mes(db: AsyncSession, empresa_id: int) -> list[Pedido]:
    """Obtiene los pedidos del mes actual."""
    hoy: date = datetime.now(UTC).date()
    primer_dia_mes: date = hoy.replace(day=1)
    return await pedido_repo.get_by_month(db, primer_dia_mes, empresa_id)


async def get_pedidos_pendientes(
    db: AsyncSession, empresa_id: int, fecha: date | None = None,
) -> list[Pedido]:
    """Obtiene pedidos pendientes para armado de entregas."""
    return await pedido_repo.get_pending_by_empresa(db, empresa_id, fecha)

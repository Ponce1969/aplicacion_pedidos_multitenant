"""CQRS Query Service — Fleteros (repartidores) con estado dinámico.

El estado "Disponible" / "En viaje" se calcula dinámicamente
verificando si el repartidor tiene pedidos activos en estado
'asignado' o 'en_camino'. NO se persiste en BD.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pedido, Usuario


@dataclass(frozen=True)
class FleteroConEstadoDTO:
    """DTO de fletero con estado calculado dinámicamente."""

    id: int
    nombre: str
    apellido: str
    email: str
    celular: str | None
    vehiculo: str | None
    is_active: bool
    estado: str  # "Disponible" o "En viaje"


async def get_fleteros_con_estado(db: AsyncSession, empresa_id: int) -> list[FleteroConEstadoDTO]:
    """Obtiene repartidores de la empresa con su estado dinámico.

    Estado "En viaje" = tiene al menos un pedido en estado 'asignado' o 'en_camino'.
    Estado "Disponible" = no tiene pedidos activos.
    """
    # Subquery: cantidad de pedidos activos (asignado/en_camino) por repartidor
    pedidos_activos = (
        select(
            Pedido.repartidor_id,
            func.count(Pedido.id).label("pedidos_activos"),
        )
        .where(
            Pedido.empresa_id == empresa_id,
            Pedido.repartidor_id.isnot(None),
            Pedido.estado.in_(["asignado", "en_camino"]),
        )
        .group_by(Pedido.repartidor_id)
        .subquery()
    )

    # Query principal: repartidores con LEFT JOIN a pedidos activos
    stmt = (
        select(
            Usuario.id,
            Usuario.nombre,
            Usuario.apellido,
            Usuario.email,
            Usuario.celular,
            Usuario.vehiculo,
            Usuario.is_active,
            func.coalesce(pedidos_activos.c.pedidos_activos, 0).label("pedidos_activos"),
        )
        .outerjoin(pedidos_activos, Usuario.id == pedidos_activos.c.repartidor_id)
        .where(
            Usuario.empresa_id == empresa_id,
            Usuario.rol == "repartidor",
        )
        .order_by(Usuario.is_active.desc(), Usuario.apellido, Usuario.nombre)
    )

    result = await db.execute(stmt)
    rows = result.all()

    fleteros: list[FleteroConEstadoDTO] = []
    for row in rows:
        estado = "En viaje" if row.pedidos_activos > 0 else "Disponible"
        fleteros.append(
            FleteroConEstadoDTO(
                id=row.id,
                nombre=row.nombre,
                apellido=row.apellido,
                email=row.email,
                celular=row.celular,
                vehiculo=row.vehiculo,
                is_active=row.is_active,
                estado=estado,
            )
        )
    return fleteros
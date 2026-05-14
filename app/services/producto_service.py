"""Servicio de negocio para productos — find_or_create (JIT Smart Ingestion).

Patrón CQRS: este servicio maneja lógica de escritura/creación de productos.
La lectura/búsqueda está en services/queries/producto_search_service.py.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Producto

logger = logging.getLogger(__name__)


def normalizar_nombre_producto(nombre: str) -> str:
    """Normaliza el nombre del producto antes de búsqueda o creación.

    Aplica .strip().title() para garantizar consistencia en el índice único
    case-insensitive (LOWER(BTRIM(nombre)) + empresa_id).
    """
    return nombre.strip().title()


async def find_or_create_producto(
    db: AsyncSession,
    empresa_id: int,
    nombre_raw: str,
    precio_unitario: Decimal,
) -> Producto:
    """Busca un producto por nombre normalizado (case-insensitive).

    Si no existe, lo crea como JIT (es_automatico=True).
    Si existe, lo devuelve SIN modificar el precio del catálogo.

    Reglas:
    - R1: Producto existe → vincular, NO actualizar precio_base
    - R2: Producto no existe → crear con es_automatico=True
    - R3: Nombre se normaliza con .strip().title()
    - R4: Precio siempre como Decimal
    - R5: Idempotente y seguro ante condiciones de carrera (IntegrityError)

    Args:
        db: Sesión de base de datos async
        empresa_id: ID de la empresa (del JWT)
        nombre_raw: Nombre del producto como lo escribió el usuario
        precio_unitario: Precio ingresado en el pedido (para crear JIT si no existe)

    Returns:
        Producto existente o recién creado
    """
    nombre_normalizado = normalizar_nombre_producto(nombre_raw)

    if not nombre_normalizado:
        raise ValueError("El nombre del producto no puede estar vacío")

    # Búsqueda case-insensitive (LOWER para matching)
    result = await db.execute(
        select(Producto).where(
            Producto.empresa_id == empresa_id,
            func.lower(func.btrim(Producto.nombre)) == nombre_normalizado.lower(),
            Producto.is_active == True,  # noqa: E712
        )
    )
    producto = result.scalar_one_or_none()

    if producto:
        # R1: Producto existe → vincular, NO actualizar precio
        logger.debug(
            "Producto existente encontrado: #%s '%s' (empresa %s)",
            producto.id,
            producto.nombre,
            empresa_id,
        )
        return producto

    # R2: Producto no existe → crear JIT
    nuevo = Producto(
        empresa_id=empresa_id,
        nombre=nombre_normalizado,
        precio_base=precio_unitario,
        es_automatico=True,
        # Campos mínimos JIT — el resto toma defaults del modelo o None:
        # sku=None, descripcion=None, categoria=None
        # stock=None (sin control hasta que admin lo configure)
        # stock_minimo=None
        # unidad_medida → server_default="unidad"
    )

    # R5: Manejar condición de carrera
    try:
        db.add(nuevo)
        await db.flush()
        logger.info(
            "Producto JIT creado: #%s '%s' (empresa %s, precio %s)",
            nuevo.id,
            nuevo.nombre,
            empresa_id,
            precio_unitario,
        )
        return nuevo
    except IntegrityError:
        # Otro request ya creó el producto — buscarlo y devolverlo
        await db.rollback()
        result = await db.execute(
            select(Producto).where(
                Producto.empresa_id == empresa_id,
                func.lower(func.btrim(Producto.nombre)) == nombre_normalizado.lower(),
                Producto.is_active == True,  # noqa: E712
            )
        )
        producto = result.scalar_one()
        logger.info(
            "Producto JIT ya existía (race condition): #%s '%s'",
            producto.id,
            producto.nombre,
        )
        return producto
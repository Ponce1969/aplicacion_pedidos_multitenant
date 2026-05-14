"""Servicio de consultas para búsqueda híbrida de productos (CQRS Query side).

Combina historial de compras del cliente con catálogo general usando
SQL nativo (sqlalchemy.text) para máxima eficiencia.

Estrategia:
1. Primero busca productos del historial del cliente (marcados como frecuentes)
2. Luego busca productos del catálogo general
3. Deduplica: si un producto aparece en ambos segmentos, prevalece el historial
4. Ordena: manuales primero (es_automatico=False), luego frecuentes, luego por nombre
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.queries.producto_search import ProductoSearchResultDTO

# SQL que combina historial + catálogo en una sola query eficiente.
# Usa CTEs para separar los segmentos y luego UNION ALL + deduplicación.
# ORDER BY: manuales primero (es_automatico ASC), frecuentes segundo, nombre tercero.
HYBRID_SEARCH_SQL = text("""
    WITH historial AS (
        -- Segmento A: Productos comprados previamente por el cliente
        SELECT DISTINCT
            p.id,
            p.nombre,
            p.precio_base AS precio_venta,
            p.unidad_medida,
            p.stock AS stock_actual,
            TRUE AS es_frecuente,
            last_pi.precio_unitario AS ultimo_precio_pactado,
            p.es_automatico
        FROM productos p
        INNER JOIN pedido_items pi ON pi.producto_id = p.id
        INNER JOIN pedidos pe ON pe.id = pi.pedido_id
        INNER JOIN (
            -- Obtener el último precio pactado por producto para este cliente
            SELECT DISTINCT ON (pi2.producto_id)
                pi2.producto_id,
                pi2.precio_unitario
            FROM pedido_items pi2
            INNER JOIN pedidos pe2 ON pe2.id = pi2.pedido_id
            WHERE pe2.cliente_id = :cliente_id
                AND pe2.empresa_id = :empresa_id
                AND pe2.estado != 'cancelado'
                AND pi2.producto_id IS NOT NULL
            ORDER BY pi2.producto_id, pe2.fecha_creacion DESC
        ) last_pi ON last_pi.producto_id = p.id
        WHERE pe.cliente_id = :cliente_id
            AND pe.empresa_id = :empresa_id
            AND pe.estado != 'cancelado'
            AND p.empresa_id = :empresa_id
            AND p.is_active = TRUE
            AND (p.nombre ILIKE :pattern OR p.sku ILIKE :pattern)
    ),
    catalogo AS (
        -- Segmento B: Productos del catálogo general
        SELECT
            p.id,
            p.nombre,
            p.precio_base AS precio_venta,
            p.unidad_medida,
            p.stock AS stock_actual,
            FALSE AS es_frecuente,
            NULL::NUMERIC AS ultimo_precio_pactado,
            p.es_automatico
        FROM productos p
        WHERE p.empresa_id = :empresa_id
            AND p.is_active = TRUE
            AND (p.nombre ILIKE :pattern OR p.sku ILIKE :pattern)
            AND p.id NOT IN (SELECT id FROM historial)
    )
    SELECT * FROM historial
    UNION ALL
    SELECT * FROM catalogo
    ORDER BY es_automatico ASC, es_frecuente DESC, nombre ASC
    LIMIT :limit
""")

# Fallback SQL cuando no hay cliente seleccionado: solo catálogo
CATALOG_ONLY_SQL = text("""
    SELECT
        p.id,
        p.nombre,
        p.precio_base AS precio_venta,
        p.unidad_medida,
        p.stock AS stock_actual,
        FALSE AS es_frecuente,
        NULL::NUMERIC AS ultimo_precio_pactado,
        p.es_automatico
    FROM productos p
    WHERE p.empresa_id = :empresa_id
        AND p.is_active = TRUE
        AND (p.nombre ILIKE :pattern OR p.sku ILIKE :pattern)
    ORDER BY p.es_automatico ASC, p.nombre ASC
    LIMIT :limit
""")


async def search_productos(
    db: AsyncSession,
    query: str,
    empresa_id: int,
    cliente_id: int | None = None,
    limit: int = 20,
) -> list[ProductoSearchResultDTO]:
    """Búsqueda híbrida de productos: historial + catálogo.

    Args:
        db: Sesión de base de datos async
        query: Texto de búsqueda ingresado por el usuario
        empresa_id: ID de la empresa (del token JWT, NO del frontend)
        cliente_id: ID del cliente seleccionado (opcional, para historial)
        limit: Máximo de resultados a retornar

    Returns:
        Lista de ProductoSearchResultDTO con productos frecuentes primero,
        luego productos del catálogo, sin duplicados.
        Manuales (es_automatico=False) siempre antes de automáticos (JIT).
    """
    # Normalizar espacios en la búsqueda (igual que en cliente_repo)
    termino = " ".join(query.split())
    pattern = f"%{termino}%"

    if cliente_id:
        # Búsqueda híbrida: historial + catálogo
        result = await db.execute(
            HYBRID_SEARCH_SQL.bindparams(
                pattern=pattern,
                empresa_id=empresa_id,
                cliente_id=cliente_id,
                limit=limit,
            )
        )
    else:
        # Sin cliente: solo catálogo
        result = await db.execute(
            CATALOG_ONLY_SQL.bindparams(
                pattern=pattern,
                empresa_id=empresa_id,
                limit=limit,
            )
        )

    rows = result.fetchall()
    return [
        ProductoSearchResultDTO(
            id=row.id,
            nombre=row.nombre,
            precio_venta=Decimal(str(row.precio_venta)),
            unidad_medida=row.unidad_medida,
            stock_actual=Decimal(str(row.stock_actual)) if row.stock_actual is not None else None,
            es_frecuente=row.es_frecuente,
            ultimo_precio_pactado=Decimal(str(row.ultimo_precio_pactado)) if row.ultimo_precio_pactado is not None else None,
            es_automatico=row.es_automatico,
        )
        for row in rows
    ]
"""Servicio de consultas para insights de clientes (CQRS Query side).

Este módulo implementa consultas consolidadas usando SQL nativo (sqlalchemy.text)
para máxima eficiencia en reportes y dashboards.

NOTA IMPORTANTE SOBRE saldo_pendiente:
- El saldo_pendiente es el TOTAL acumulado desde cliente.saldo_pendiente
- NO está filtrado por el parámetro 'dias'
- Los totales (total_pedidos, total_vendido, total_senia) SÍ están filtrados por días
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.queries.cliente_insights import (
    ConsolidadoProductoDTO,
    InsightConsolidadoDTO,
    InsightPedidoDTO,
    InsightPedidosDTO,
)


async def get_consolidado(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
    dias: int,
) -> InsightConsolidadoDTO:
    """Obtiene datos consolidados del cliente con métricas del período.

    Args:
        db: Sesión de base de datos async
        cliente_id: ID del cliente a consultar
        empresa_id: ID de la empresa (del token de auth, NO del frontend)
        dias: Cantidad de días hacia atrás para filtrar pedidos

    Returns:
        InsightConsolidadoDTO con datos del cliente y métricas del período
    """
    # Query 1: Datos del cliente + totales del período
    sql_cliente = text("""
        SELECT
            c.id,
            c.nombre,
            c.apellido,
            c.celular,
            c.saldo_pendiente,
            c.limite_credito,
            COUNT(p.id) AS total_pedidos,
            COALESCE(SUM(p.total), 0) AS total_vendido,
            COALESCE(SUM(p.senia), 0) AS total_senia
        FROM clientes c
        LEFT JOIN pedidos p ON p.cliente_id = c.id
            AND p.empresa_id = :empresa_id
            AND p.fecha_creacion >= NOW() - INTERVAL '1 day' * :dias
            AND p.estado != 'cancelado'
        WHERE c.id = :cliente_id
            AND c.empresa_id = :empresa_id
        GROUP BY c.id
    """).bindparams(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        dias=dias,
    )

    result_cliente = await db.execute(sql_cliente)
    row_cliente = result_cliente.fetchone()

    if row_cliente is None:
        # Cliente no existe o no pertenece a la empresa
        raise ValueError(f"Cliente {cliente_id} no encontrado en empresa {empresa_id}")

    # Query 2: Productos agrupados del período
    sql_productos = text("""
        SELECT
            pi.descripcion AS producto_descripcion,
            SUM(pi.cantidad) AS cantidad_total,
            SUM(pi.subtotal) AS monto_total,
            MAX(p.fecha_creacion)::date AS ultima_compra
        FROM pedido_items pi
        JOIN pedidos p ON p.id = pi.pedido_id
        WHERE p.cliente_id = :cliente_id
            AND p.empresa_id = :empresa_id
            AND p.fecha_creacion >= NOW() - INTERVAL '1 day' * :dias
            AND p.estado != 'cancelado'
        GROUP BY pi.descripcion
        ORDER BY monto_total DESC
        LIMIT 50
    """).bindparams(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        dias=dias,
    )

    result_productos = await db.execute(sql_productos)
    rows_productos = result_productos.fetchall()

    # Mapear productos a DTOs
    productos = [
        ConsolidadoProductoDTO(
            producto_descripcion=row.producto_descripcion,
            cantidad_total=float(row.cantidad_total),
            monto_total=Decimal(str(row.monto_total)),
            ultima_compra=row.ultima_compra,
        )
        for row in rows_productos
    ]

    # Construir DTO consolidado
    return InsightConsolidadoDTO(
        cliente_id=row_cliente.id,
        cliente_nombre=row_cliente.nombre,
        cliente_apellido=row_cliente.apellido,
        cliente_celular=row_cliente.celular,
        saldo_pendiente=Decimal(str(row_cliente.saldo_pendiente or 0)),
        limite_credito=Decimal(str(row_cliente.limite_credito)) if row_cliente.limite_credito else None,
        total_pedidos=row_cliente.total_pedidos or 0,
        total_vendido=Decimal(str(row_cliente.total_vendido or 0)),
        total_senia=Decimal(str(row_cliente.total_senia or 0)),
        productos=productos,
    )


async def get_pedidos(
    db: AsyncSession,
    cliente_id: int,
    empresa_id: int,
    dias: int,
) -> InsightPedidosDTO:
    """Obtiene la lista de pedidos del cliente en el período especificado.

    Args:
        db: Sesión de base de datos async
        cliente_id: ID del cliente a consultar
        empresa_id: ID de la empresa (del token de auth, NO del frontend)
        dias: Cantidad de días hacia atrás para filtrar pedidos

    Returns:
        InsightPedidosDTO con lista de pedidos del período
    """
    # Query: Pedidos del período (incluye cancelados para ver historial completo)
    sql_pedidos = text("""
        SELECT
            p.id,
            p.fecha_creacion::date AS fecha,
            p.total,
            p.senia,
            p.estado,
            p.estado_pago
        FROM pedidos p
        WHERE p.cliente_id = :cliente_id
            AND p.empresa_id = :empresa_id
            AND p.fecha_creacion >= NOW() - INTERVAL '1 day' * :dias
        ORDER BY p.fecha_creacion DESC
        LIMIT 100
    """).bindparams(
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        dias=dias,
    )

    result_pedidos = await db.execute(sql_pedidos)
    rows_pedidos = result_pedidos.fetchall()

    # Si no hay pedidos, necesitamos al menos los datos del cliente
    if not rows_pedidos:
        sql_cliente = text("""
            SELECT nombre, apellido
            FROM clientes
            WHERE id = :cliente_id AND empresa_id = :empresa_id
        """).bindparams(
            cliente_id=cliente_id,
            empresa_id=empresa_id,
        )
        result_cliente = await db.execute(sql_cliente)
        row_cliente = result_cliente.fetchone()
        if row_cliente is None:
            raise ValueError(f"Cliente {cliente_id} no encontrado en empresa {empresa_id}")
        nombre = row_cliente.nombre
        apellido = row_cliente.apellido
    else:
        # Tomar nombre/apellido del primer pedido (mismo cliente)
        nombre = ""
        apellido = ""
        # Los obtendremos del resultado consolidado si es necesario
        sql_cliente = text("""
            SELECT nombre, apellido
            FROM clientes
            WHERE id = :cliente_id AND empresa_id = :empresa_id
        """).bindparams(
            cliente_id=cliente_id,
            empresa_id=empresa_id,
        )
        result_cliente = await db.execute(sql_cliente)
        row_cliente = result_cliente.fetchone()
        if row_cliente:
            nombre = row_cliente.nombre
            apellido = row_cliente.apellido

    # Mapear pedidos a DTOs
    pedidos = [
        InsightPedidoDTO(
            pedido_id=row.id,
            fecha=row.fecha,
            total=Decimal(str(row.total or 0)),
            senia=Decimal(str(row.senia or 0)),
            estado=row.estado,
            estado_pago=row.estado_pago,
        )
        for row in rows_pedidos
    ]

    return InsightPedidosDTO(
        cliente_id=cliente_id,
        cliente_nombre=nombre,
        cliente_apellido=apellido,
        pedidos=pedidos,
    )

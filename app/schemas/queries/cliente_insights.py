"""DTOs para consultas de insights de clientes (CQRS Query side).

Este módulo contiene los Data Transfer Objects utilizados para retornar
datos consolidados de clientes sin exponer los modelos ORM directamente.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal


class ConsolidadoProductoDTO:
    """Producto agrupado en el consolidado de compras del cliente."""

    def __init__(
        self,
        producto_descripcion: str,
        cantidad_total: float,
        monto_total: Decimal,
        ultima_compra: date | None,
    ) -> None:
        self.producto_descripcion = producto_descripcion
        self.cantidad_total = cantidad_total
        self.monto_total = monto_total
        self.ultima_compra = ultima_compra


class InsightConsolidadoDTO:
    """DTO consolidado con métricas del cliente.

    IMPORTANTE: El saldo_pendiente es el TOTAL acumulado (NO filtrado por días),
    mientras que total_pedidos, total_vendido y total_senia SÍ están filtrados
    por el período especificado en días.
    """

    def __init__(
        self,
        cliente_id: int,
        cliente_nombre: str,
        cliente_apellido: str,
        cliente_celular: str,
        saldo_pendiente: Decimal,
        limite_credito: Decimal | None,
        total_pedidos: int,
        total_vendido: Decimal,
        total_senia: Decimal,
        productos: list[ConsolidadoProductoDTO],
    ) -> None:
        self.cliente_id = cliente_id
        self.cliente_nombre = cliente_nombre
        self.cliente_apellido = cliente_apellido
        self.cliente_celular = cliente_celular
        self.saldo_pendiente = saldo_pendiente
        self.limite_credito = limite_credito
        self.total_pedidos = total_pedidos
        self.total_vendido = total_vendido
        self.total_senia = total_senia
        self.productos = productos


class InsightPedidoDTO:
    """Pedido individual en la lista de pedidos del cliente."""

    def __init__(
        self,
        pedido_id: int,
        fecha: date,
        total: Decimal,
        senia: Decimal,
        estado: str,
        estado_pago: str,
    ) -> None:
        self.pedido_id = pedido_id
        self.fecha = fecha
        self.total = total
        self.senia = senia
        self.estado = estado
        self.estado_pago = estado_pago


class InsightPedidosDTO:
    """DTO con lista de pedidos del cliente."""

    def __init__(
        self,
        cliente_id: int,
        cliente_nombre: str,
        cliente_apellido: str,
        pedidos: list[InsightPedidoDTO],
    ) -> None:
        self.cliente_id = cliente_id
        self.cliente_nombre = cliente_nombre
        self.cliente_apellido = cliente_apellido
        self.pedidos = pedidos

"""DTOs para búsqueda híbrida de productos (CQRS Query side).

Combina historial de compras del cliente con catálogo general,
priorizando productos frecuentes y deduplicando resultados.
"""

from __future__ import annotations

from decimal import Decimal


class ProductoSearchResultDTO:
    """Producto resultado de búsqueda híbrida.

    Puede provenir del historial del cliente (es_frecuente=True)
    o del catálogo general (es_frecuente=False).
    """

    def __init__(
        self,
        id: int,
        nombre: str,
        precio_venta: Decimal,
        unidad_medida: str,
        stock_actual: Decimal | None,
        es_frecuente: bool,
        ultimo_precio_pactado: Decimal | None = None,
    ) -> None:
        self.id = id
        self.nombre = nombre
        self.precio_venta = precio_venta
        self.unidad_medida = unidad_medida
        self.stock_actual = stock_actual
        self.es_frecuente = es_frecuente
        self.ultimo_precio_pactado = ultimo_precio_pactado
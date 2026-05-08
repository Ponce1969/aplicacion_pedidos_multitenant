# Propuesta: Búsqueda Híbrida de Productos

**Cambio**: `hybrid-product-search`
**Fecha**: 2026-05-08
**Estado**: proposed

## Intent

Combinar historial de compras del cliente con el catálogo general en la búsqueda de productos de "Nuevo Pedido", priorizando productos frecuentes y reduciendo el tiempo de búsqueda del vendedor.

## Scope

### Incluido
- Query Service en `app/services/queries/producto_search_service.py` con SQL nativo
- DTOs en `app/schemas/queries/producto_search.py`
- Modificación del endpoint `/api/productos/buscar` para aceptar `cliente_id`
- Actualización de `productos_resultado.html` con ⭐ y 📦
- Actualización de `nuevo_pedido.html` para pasar `cliente_id` en la búsqueda

### NO incluido
- Carga masiva de catálogo (futuro)
- Modificación del modelo Producto
- Nuevas migraciones

## Approach

1. SQL nativo con UNION: primero productos del historial del cliente (marcados ⭐), luego productos del catálogo no duplicados (📦)
2. `cliente_id` del JS del formulario (ya seleccionado) + `empresa_id` del JWT
3. Template con indicadores sutiles ⭐ y 📦
4. `ultimo_precio_pactado` on el último precio en pedido_items de ese cliente

## Rollback Plan

Revertir 4 archivos del endpoint y template. Sin migraciones.

## Risks

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Performance con muchos items | Medio | LIMIT 20, índices existentes |
| cliente_id no seleccionado | Bajo | Fallback a catálogo sin historial |
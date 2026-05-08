# Design: Búsqueda Híbrida de Productos

**Cambio**: `hybrid-product-search`

## Arquitectura

Patrón CQRS (Ya establecido en el proyecto):
- **Query Service**: `app/services/queries/producto_search_service.py`
- **DTO**: `app/schemas/queries/producto_search.py`
- **SQL Nativo**: `sqlalchemy.text` con CTEs y UNION ALL

## Decisión de diseño: CTE con Unión

En vez de dos queries separadas al backend, usamos UNA sola query con CTEs:

```sql
WITH historial AS (...), catalogo AS (... donde NOT IN historial)
SELECT * FROM historial UNION ALL SELECT * FROM catalogo
ORDER BY es_frecuente DESC, nombre ASC LIMIT :limit
```

**Ventaja**: Una sola ronda a la DB, deduplicación en SQL puro, orden garantizado.

## Decisión de diseño: DISTINCT ON para último precio

PostgreSQL `DISTINCT ON (producto_id) ... ORDER BY fecha_creacion DESC` obtiene
eficientemente el último precio pactado por producto sin self-joins complejos.

## Decisión de diseño: hx-vals con JS dinámico

Usamos `hx-vals="js:getProductoSearchParams()"` para incluir `cliente_id`
dinámicamente solo cuando está seleccionado. Si está vacío, se omite el parámetro
y el endpoint cae al modo catálogo-only.

## Decisión de diseño: ultimo_precio_pactado como precio sugerido

Cuando el vendedor selecciona un producto frecuente, el precio unitario se pre-llena
con el último precio pactado (si existe). Esto acelera la venta y mantiene
continuidad comercial.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/schemas/queries/producto_search.py` | NUEVO - DTOs |
| `app/services/queries/producto_search_service.py` | NUEVO - Query Service |
| `app/api/routers/pedidos.py` | Modificado - endpoint usa Query Service |
| `app/templates/partials/productos_resultado.html` | Modificado - ⭐📦, último precio, stock |
| `app/templates/nuevo_pedido.html` | Modificado - hx-vals, agregarProducto |

## Sin migraciones

No se agregan columnas ni tablas. Todo se resuelve con datos existentes en
`productos`, `pedidos`, y `pedido_items`.
# Spec: Búsqueda Híbrida de Productos

**Cambio**: `hybrid-product-search`
**Fecha**: 2026-05-08

## Requisitos

### FR-1: Endpoint de búsqueda híbrida
- `GET /api/productos/buscar` acepta `q` (string) y `cliente_id` (int, opcional)
- `empresa_id` siempre del JWT
- Si `cliente_id` está presente: busca historial + catálogo, deduplica, prioriza frecuentes
- Si no: solo catálogo (comportamiento actual)

### FR-2: Segmento A — Historial del cliente
- Productos comprados previamente por el cliente que coinciden con la query
- `es_frecuente = True`
- `ultimo_precio_pactado`: último precio en pedido_items de ese cliente/producto
- Aparecen primero en resultados

### FR-3: Segmento B — Catálogo general
- Productos activos de la empresa que coinciden con la query
- `es_frecuente = False`
- Se excluyen los que ya están en Segmento A (deduplicación)

### FR-4: DTO de respuesta
| Campo | Tipo | Requerido |
|-------|------|-----------|
| id | int | Sí |
| nombre | string | Sí |
| precio_venta | Decimal | Sí |
| unidad_medida | string | Sí |
| stock_actual | Decimal/null | Sí |
| es_frecuente | bool | Sí |
| ultimo_precio_pactado | Decimal/null | No |

### FR-5: UI — Dropdown de resultados
- ⭐ para productos frecuentes (sutil)
- 📦 para productos de catálogo
- `últ:` muestra último precio pactado si existe
- ⚠ en rojo si stock_actual < 0

### FR-6: Al seleccionar producto frecuente
- Si `ultimo_precio_pactado` existe, se usa como precio unitario del item
- Si no, se usa `precio_venta` del catálogo

### FR-7: Seguridad
- `empresa_id` SIEMPRE del JWT, nunca del frontend
- `cliente_id` viene del formulario (ya seleccionado)
- Sin catálogo cargado: Segmento B vacío, Segmento A funciona normal

## Escenarios

### Escenario 1: Cliente seleccionado, producto en historial
- Given: cliente_id=5, query="varilla"
- When: GET /api/productos/buscar?q=varilla&cliente_id=5
- Then: producto aparece con ⭐, ultimo_precio_pactado con el último precio

### Escenario 2: Cliente seleccionado, producto solo en catálogo
- Given: cliente_id=5, query="cemento"
- When: GET /api/productos/buscar?q=cemento&cliente_id=5
- Then: producto aparece con 📦, ultimo_precio_pactado=null

### Escenario 3: Producto en ambos segmentos (deduplicación)
- Given: cliente_id=5, query="varilla"
- When: GET /api/productos/buscar?q=varilla&cliente_id=5
- Then: producto aparece UNA vez con ⭐ y ultimo_precio_pactado

### Escenario 4: Sin cliente seleccionado
- Given: query="varilla"
- When: GET /api/productos/buscar?q=varilla
- Then: todos los productos con 📦, sin historial

### Escenario 5: Stock negativo
- Given: producto con stock_actual=-5
- When: aparece en dropdown
- Then: muestra ⚠ sin stock en rojo
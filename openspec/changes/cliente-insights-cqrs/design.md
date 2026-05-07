# Design: CQRS Client Insights & Historial Consolidado

**Cambio**: `cliente-insights-cqrs`
**Fecha**: 2026-05-08
**Estado**: design

## Architecture Decision Records

### ADR-001: Query Services separados de Write Services

**Contexto**: Actualmente todos los services están en `app/services/` y mezclan lectura y escritura.
**Decisión**: Crear `app/services/queries/` para lógica de lectura pura. Los services existentes quedan como write-side.
**Consecuencias**: 
- Separación clara de responsabilidades
- Los query services usan SQL nativo (`sqlalchemy.text`), los write services siguen con ORM
- Futuros reportes siguen el mismo patrón

### ADR-002: DTOs en `app/schemas/queries/`

**Contexto**: `app/schemas.py` tiene DTOs de entrada/salida mezclados.
**Decisión**: Crear `app/schemas/queries/` para DTOs de lectura. Son modelos Pydantic planos sin lógica.
**Consecuencias**: No se modifica `schemas.py` existente. Fácil de extender.

### ADR-003: Saldo pendiente = deuda total, no filtrada por días

**Contexto**: El consumo se filtra por rango de días (30 default), pero la deuda es acumulativa.
**Decisión**: En `InsightConsolidadoDTO`, `saldo_pendiente` viene directamente de `cliente.saldo_pendiente` (campo en la tabla), no se calcula filtrando pedidos. El total_vendido y total_senia SÍ se filtran por `dias`.
**Consecuencias**: El usuario ve "Gastó $X en los últimos 30 días" pero "Debe $Y en total".

### ADR-004: HTMX tab async con hx-get

**Contexto**: El insight se muestra como tab dentro de la búsqueda/ficha del cliente.
**Decisión**: La tab carga vía `hx-get="/api/clientes/{id}/insights"` con `hx-trigger="load"`. El selector de tipo (consolidado/pedidos) y rango de dias se renderizan dentro del partial.
**Consecuencias**: No sobrecarga la página principal. Solo carga datos cuando el usuario navega a esa tab.

## Component Design

### 1. DTOs (`app/schemas/queries/cliente_insights.py`)

```python
class ConsolidadoProductoDTO(BaseModel):
    producto_descripcion: str
    cantidad_total: float
    monto_total: Decimal
    ultima_compra: date | None

class InsightConsolidadoDTO(BaseModel):
    cliente_id: int
    cliente_nombre: str
    cliente_apellido: str
    cliente_celular: str
    saldo_pendiente: Decimal       # ← deuda TOTAL (no filtrada por dias)
    limite_credito: Decimal | None
    total_pedidos: int              # ← filtrado por dias
    total_vendido: Decimal         # ← filtrado por dias
    total_senia: Decimal           # ← filtrado por dias
    productos: list[ConsolidadoProductoDTO]

class InsightPedidoDTO(BaseModel):
    pedido_id: int
    fecha: date
    total: Decimal
    senia: Decimal
    estado: str
    estado_pago: str

class InsightPedidosDTO(BaseModel):
    cliente_id: int
    cliente_nombre: str
    cliente_apellido: str
    pedidos: list[InsightPedidoDTO]
```

### 2. Query Service (`app/services/queries/cliente_insights_service.py`)

**get_consolidado(db, cliente_id, empresa_id, dias)**:
1. Query 1: Datos del cliente (saldo_pendiente, limite_credito) — directo desde tabla `clientes`
2. Query 2: Agregados de pedidos (COUNT, SUM total, SUM senia) filtrado por `dias` y `empresa_id`
3. Query 3: Productos agrupados (descripcion, SUM cantidad, SUM subtotal, MAX fecha) filtrado por `dias` y `empresa_id`
4. Mapear resultados a `InsightConsolidadoDTO`

**get_pedidos(db, cliente_id, empresa_id, dias)**:
1. Query: Pedidos ordenados por fecha desc, filtrado por `dias` y `empresa_id`, LIMIT 100
2. Mapear a `InsightPedidosDTO`

**Ambas queries**:
- `empresa_id` viene del JWT, nunca del frontend
- cliente_id se valida contra empresa_id (404 si no pertenece)
- `dias` se valida: 1-365, default 30
- Parámetros bindados con `:param` (sin concatenación de strings)

### 3. Router (`app/api/routers/clientes.py`)

```
GET /api/clientes/{cliente_id}/insights?type=consolidado|pedidos&dias=30

Auth: Depends(get_current_user)
DB: Depends(get_db)

1. Validar params (type, dias)
2. Verificar cliente existe y pertenece a empresa → 404 si no
3. Dispatch a service según type
4. Renderizar partial HTMX con datos
```

### 4. HTMX Partial (`app/templates/partials/cliente_insights.html`)

Estructura:
- Select de tipo (consolidado / pedidos) con `hx-get` que re-renderiza el partial
- Select de rango de dias (7, 15, 30, 60, 90, 365)
- Contenido según tipo

**Consolidado**:
```
┌─────────────────────────────────────────────┐
│ 📊 Resumen de Pedro Marmol                 │
│ Celular: 096787889                          │
│ Saldo pendiente: $45.000 (TOTAL)    │
│ Límite de crédito: $100.000                │
├─────────────────────────────────────────────┤
│ Últimos 30 días:                           │
│ Pedidos: 5  Vendido: $120.000  Seña: $75.000│
├─────────────────────────────────────────────┤
│ Productos:                                  │
│ Descripción  | Cant | Monto  | Últ.Compra  │
│ Cemento      |  50  | $25.000| 05/05/2026  │
│ Arena        |  10  | $15.000| 03/05/2026  │
│ ...                                         │
└─────────────────────────────────────────────┘
```

**Pedidos**:
```
┌─────────────────────────────────────────────┐
│ 📋 Pedidos de Pedro Marmol                 │
│ [7d] [15d] [30d] [60d] [90d] [TODO]        │
├─────────────────────────────────────────────┤
│ #14 | 08/05 | $25.000 | Seña $10.000 | ⏳  │
│ #11 | 03/05 | $15.000 | Pago total    | ✅  │
│ ...                                         │
└─────────────────────────────────────────────┘
```

### 5. Wiring en `app/main.py`

Incluir el router: `app.include_router(clientes_router)`

## Interaction Sequence

```
Usuario → Click en cliente (buscar.html)
        → HTMX: GET /api/clientes/{id}/insights?type=consolidado&dias=30
        → Router valida auth + empresa
        → Query Service ejecuta SQL nativo
        → Mapea a DTO
        → Jinja2 renderiza partial
        → HTMX swapea en el DOM
```

## SQL Queries (Final)

### Consolidado — Cliente + Agregados

```sql
SELECT
    c.id, c.nombre, c.apellido, c.celular,
    c.saldo_pendiente, c.limite_credito,
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
GROUP BY c.id;
```

### Consolidado — Productos

```sql
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
LIMIT 50;
```

### Pedidos — Lista cronológica

```sql
SELECT
    p.id, p.fecha_creacion::date AS fecha,
    p.total, p.senia, p.estado, p.estado_pago
FROM pedidos p
WHERE p.cliente_id = :cliente_id
    AND p.empresa_id = :empresa_id
    AND p.fecha_creacion >= NOW() - INTERVAL '1 day' * :dias
ORDER BY p.fecha_creacion DESC
LIMIT 100;
```

## Security Checklist

- [x] empresa_id from JWT token only (Depends(get_current_user))
- [x] cliente_id verified against empresa_id (404 if mismatch)
- [x] SQL parameters binded with `:param` (no string concatenation)
- [x] dias validated: 1-365
- [x] type validated: consolidado|pedidos
- [x] CSRF exempt: GET requests are naturally exempt (no state mutation)

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `app/schemas/queries/__init__.py` | CREATE | Package init |
| `app/schemas/queries/cliente_insights.py` | CREATE | DTOs |
| `app/services/queries/__init__.py` | CREATE | Package init |
| `app/services/queries/cliente_insights_service.py` | CREATE | Query Service |
| `app/api/routers/clientes.py` | CREATE | Router with auth |
| `app/templates/partials/cliente_insights.html` | CREATE | HTMX partial |
| `app/main.py` | MODIFY | Include new router |
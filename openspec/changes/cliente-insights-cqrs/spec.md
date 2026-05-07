# Spec: CQRS Client Insights & Historial Consolidado

**Cambio**: `cliente-insights-cqrs`
**Fecha**: 2026-05-08
**Estado**: spec

## Overview

Un endpoint de lectura `GET /api/clientes/{cliente_id}/insights` que devuelve insights de un cliente vía HTMX partials, usando un Query Service CQRS con SQL nativo optimizado.

## Architecture Decision

**ADR-001**: Separar lógica de lectura (queries) de la lógica de escritura (commands).

- **Rationale**: Las queries agregadas (GROUP BY, SUM, COUNT) son ineficientes con ORM. SQL nativo permite controlar exactamente qué se consulta y optimizar con índices.
- **Consecuencias**: Se crea un nuevo módulo `app/services/queries/` dedicado exclusivamente a lectura. Los services existentes en `app/services/` quedan como commands/write-side.

**ADR-002**: Usar `sqlalchemy.text` con parámetros bindados para queries consolidadas.

- **Rationale**: Evita SQL injection y permite al motor de DB optimizar el plan de ejecución.
- **Consecuencias**: Las queries son más verbosas pero seguras y performantes.

**ADR-003**: `empresa_id` SIEMPRE proviene del JWT token via `current_user.empresa_id`.

- **Rationale**: Previene cross-tenant data leakage. Un usuario de empresa A nunca puede ver datos de empresa B.
- **Consecuencias**: El parámetro no es configurable desde el frontend. Cualquier intento de manipularlo resulta en 403 o datos vacíos.

## API Contract

### Endpoint

```
GET /api/clientes/{cliente_id}/insights?type={consolidado|pedidos}&dias={1-365}
```

**Parameters**:
- `type` (required): `consolidado` o `pedidos`
- `dias` (optional, default=30): rango de días hacia atrás

**Auth**: Requiere JWT válido (cookie `access_token` o header `Authorization: Bearer`)

**Response**: HTML partial (HTMX), no JSON

### Error Responses

- `404`: Cliente no encontrado o no pertenece a la empresa del usuario
- `422`: Parámetros inválidos (type fuera de rango, dias fuera de rango)

## Data Models

### DTOs (`app/schemas/queries/cliente_insights.py`)

```python
class ConsolidadoProductoDTO(BaseModel):
    """Un producto en el resumen consolidado del cliente."""
    producto_descripcion: str
    cantidad_total: float
    monto_total: float
    ultima_compra: date | None  # MAX(fecha) de ese producto

class InsightConsolidadoDTO(BaseModel):
    """Resumen consolidado del cliente."""
    cliente_id: int
    cliente_nombre: str
    cliente_apellido: str
    cliente_celular: str
    saldo_pendiente: Decimal
    limite_credito: Decimal | None
    total_pedidos: int
    total_vendido: Decimal
    total_senia: Decimal
    productos: list[ConsolidadoProductoDTO]

class InsightPedidoDTO(BaseModel):
    """Un pedido en la lista cronológica."""
    pedido_id: int
    fecha: date
    total: Decimal
    senia: Decimal
    estado: str
    estado_pago: str

class InsightPedidosDTO(BaseModel):
    """Lista cronológica de pedidos del cliente."""
    cliente_id: int
    cliente_nombre: str
    cliente_apellido: str
    pedidos: list[InsightPedidoDTO]
```

## Scenarios

### Scenario 1: Consolidado con datos

**Given** un cliente con ID=5 en empresa_id=3 que hizo 4 pedidos en los últimos 30 días
**When** `GET /api/clientes/5/insights?type=consolidado&dias=30`
**Then** devuelve HTML con:
- Nombre, apellido, celular del cliente
- Saldo pendiente y límite de crédito
- Total pedidos: 4, Total vendido: suma de totales, Total seña: suma de señas
- Lista de productos con cantidad total, monto total y fecha de última compra
- Cada fila de producto muestra descripción, cantidad, monto y fecha

### Scenario 2: Consolidado sin datos

**Given** un cliente que no hizo pedidos en los últimos 30 días
**When** `GET /api/clientes/5/insights?type=consolidado&dias=30`
**Then** devuelve HTML con datos del cliente, totales en 0, lista de productos vacía con mensaje "Sin pedidos en los últimos 30 días"

### Scenario 3: Pedidos cronológicos

**Given** un cliente con ID=5 en empresa_id=3
**When** `GET /api/clientes/5/insights?type=pedidos&dias=30`
**Then** devuelve HTML con lista de pedidos ordenados por fecha descendente, cada uno con: ID, fecha, total, seña, estado, estado_pago

### Scenario 4: Cliente de otra empresa (aislamiento multi-tenant)

**Given** un cliente con ID=5 que pertenece a empresa_id=3
**And** un usuario autenticado con empresa_id=4
**When** `GET /api/clientes/5/insights?type=consolidado&dias=30`
**Then** devuelve 404 "Cliente no encontrado"

### Scenario 5: Parámetros inválidos

**When** `GET /api/clientes/5/insights?type=invalido&dias=30`
**Then** devuelve 422 error de validación

**When** `GET /api/clientes/5/insights?type=consolidado&dias=500`
**Then** devuelve 422 error de validación (dias max=365)

### Scenario 6: Usuario no autenticado

**When** `GET /api/clientes/5/insights?type=consolidado` sin cookie ni header de auth
**Then** redirige a /login (comportamiento estándar del auth dependency)

## Native SQL Queries

### Consolidado

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
  AND p.fecha_creacion >= NOW() - INTERVAL ':dias days'
  AND p.estado != 'cancelado'
GROUP BY pi.descripcion
ORDER BY monto_total DESC
LIMIT 50;
```

Plus a separate query for client totals:

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
    AND p.fecha_creacion >= NOW() - INTERVAL ':dias days'
    AND p.estado != 'cancelado'
WHERE c.id = :cliente_id
  AND c.empresa_id = :empresa_id
GROUP BY c.id;
```

### Pedidos (lista cronológica)

```sql
SELECT
    p.id, p.fecha_creacion::date AS fecha,
    p.total, p.senia, p.estado, p.estado_pago
FROM pedidos p
WHERE p.cliente_id = :cliente_id
  AND p.empresa_id = :empresa_id
  AND p.fecha_creacion >= NOW() - INTERVAL ':dias days'
ORDER BY p.fecha_creacion DESC
LIMIT 100;
```

## Files to Create/Modify

### New Files
1. `app/schemas/queries/__init__.py`
2. `app/schemas/queries/cliente_insights.py` — DTOs
3. `app/services/queries/__init__.py`
4. `app/services/queries/cliente_insights_service.py` — Query Service
5. `app/api/routers/clientes.py` — Router dispatcher
6. `app/templates/partials/cliente_insights.html` — HTMX partial

### Modified Files
7. `app/main.py` — Include new `clientes` router

### No Changes
- No migrations needed
- No existing endpoints modified
- No models modified
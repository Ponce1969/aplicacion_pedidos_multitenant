# Propuesta: CQRS Client Insights & Historial Consolidado

**Cambio**: `cliente-insights-cqrs`
**Fecha**: 2026-05-08
**Estado**: proposed

## Intent

Implementar un Query Service CQRS para insights de clientes que establezca un patrón limpio y reutilizable para futuros reportes, usando SQL nativo para consultas agregadas y HTMX tabs para la UI.

## Scope

### Incluido
- `app/schemas/queries/cliente_insights.py` — DTOs Pydantic planos
- `app/services/queries/cliente_insights_service.py` — Query Service con SQL nativo
- `app/api/routers/clientes.py` — Endpoint dispatcher con auth
- `app/templates/partials/cliente_insights.html` — HTMX partial con tabs
- Extensión de `buscar.html` o similar para agregar tab de insights por cliente

### NO incluido
- Modificación de endpoints existentes
- Nuevas migraciones de DB (todos los campos ya existen)
- Dashboard de reportes globales (futura iteración)
- API REST JSON (solo HTMX partials por ahora)

## Approach

1. **Separación CQRS**: Query Services en `app/services/queries/`, DTOs en `app/schemas/queries/`
2. **SQL nativo**: `sqlalchemy.text` con `GROUP BY` para `consolidado`, parametrizado con `:empresa_id` y `:dias`
3. **Seguridad multitenant**: `empresa_id` SIEMPRE del token JWT (`current_user.empresa_id`), nunca del frontend
4. **HTMX tabs**: Tab asíncrona dentro de la ficha/búsqueda del cliente, carga vía `hx-get`
5. **Types**: `consolidado` (totales por producto con `ultima_compra`) y `pedidos` (lista cronológica)

## Rollback Plan

Eliminar los 4 archivos nuevos. No hay migraciones ni cambios en datos existentes. Borrar y listo.

## Risks

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Fuga multi-tenant | Crítico | `empresa_id` siempre del JWT, nunca del query param |
| Performance con datasets grandes | Medio | `dias` capped at 365, `LIMIT 100` en pedidos |
| SQL injection | Crítico | Usar `:parametros` bindados, nunca concatenar strings |

## Next Phase

`sdd-spec` — Escribir especificaciones formales con escenarios Given/When/Then
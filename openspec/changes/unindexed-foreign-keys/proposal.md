# Propuesta: Indexación de Foreign Keys Críticas (Unindexed FKs)

**Fecha:** 2026-09-24  
**Origen:** Auditoría Determinista de Salud PostgreSQL con `mcp_pg_auditor`  
**Proyecto:** Aplicación Pedidos Multitenant (`barraca_pedidos`)  
**Base de Datos:** PostgreSQL 16 (`barraca`)

---

## 1. Contexto y Diagnóstico

Durante la auditoría de rendimiento y bloqueos ejecutada contra la base de datos de producción `barraca`, el motor detectó **2 Foreign Keys sin índice B-Tree secundario en su prefijo izquierdo**.

### Riesgo Técnico en Producción:
1. **Table-level Locks (`SHARE ROW EXCLUSIVE`):**  
   Cuando se ejecuta un `DELETE` o `UPDATE` sobre la clave primaria de la tabla padre (`usuarios`), PostgreSQL debe verificar la integridad referencial en las tablas hijas (`entrega_eventos` y `pagos`). Al no existir un índice en la columna foránea, el motor se ve obligado a realizar un **Sequential Scan** sobre toda la tabla hija y adquirir bloqueos a nivel de tabla, congelando transacciones concurrentes.
2. **Degradación en JOINs frecuentes:**  
   Las consultas operativas que cruzan entregas o pagos por usuario sufren escaneos completos en lugar de búsquedas por índice (*Index Scan* / *Bitmap Index Scan*).

---

## 2. Foreign Keys No Indizadas Detectadas

| Tabla Hija | Columna FK | Constraint | Tabla Padre |
|---|---|---|---|
| `entrega_eventos` | `usuario_id` | `entrega_eventos_usuario_id_fkey` | `usuarios(id)` |
| `pagos` | `registrado_por` | `pagos_registrado_por_fkey` | `usuarios(id)` |

---

## 3. Plan de Remediación

### DDL Recomendado (Cero Downtime en PostgreSQL):
Ejecutar sentencias `CONCURRENTLY` bajo bloque de autocommit en Alembic para no bloquear lecturas ni escrituras durante la creación:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_evento_usuario 
    ON entrega_eventos (usuario_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pago_registrado_por 
    ON pagos (registrado_por);
```

### Tareas:
- [x] Generar migración de Alembic en `alembic/versions/` (revisión `015`) aplicando los dos índices concurrentemente en PostgreSQL y con fallback para SQLite/tests.
- [x] Asegurar que los modelos SQLAlchemy en `app/models.py` declaren explícitamente los índices en `__table_args__`.
- [ ] Aplicar migración en staging y verificar con `uv run mcp_pg_auditor.py --cli`.

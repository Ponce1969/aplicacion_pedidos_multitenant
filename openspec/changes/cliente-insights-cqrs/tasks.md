# Tasks: CQRS Client Insights & Historial Consolidado

**Cambio**: `cliente-insights-cqrs`
**Fecha**: 2026-05-08
**Estado**: tasks

## Phase 1: Infrastructure

### 1.1 Create query packages
- [ ] Create `app/schemas/queries/__init__.py` (empty)
- [ ] Create `app/services/queries/__init__.py` (empty)

## Phase 2: DTOs

### 2.1 Create client insights DTOs
- [ ] Create `app/schemas/queries/cliente_insights.py`
- [ ] Define `ConsolidadoProductoDTO` (producto_descripcion, cantidad_total, monto_total, ultima_compra)
- [ ] Define `InsightConsolidadoDTO` (cliente data + saldo_pendiente TOTAL + aggregated totals + productos list)
- [ ] Define `InsightPedidoDTO` (pedido_id, fecha, total, senia, estado, estado_pago)
- [ ] Define `InsightPedidosDTO` (cliente data + pedidos list)
- [ ] Key: `saldo_pendiente` is from `cliente.saldo_pendiente` (TOTAL debt, NOT filtered by dias)

## Phase 3: Query Service

### 3.1 Create cliente insights query service
- [ ] Create `app/services/queries/cliente_insights_service.py`
- [ ] Implement `get_consolidado(db, cliente_id, empresa_id, dias)`:
  - Query 1: Client data + totals from `clientes` LEFT JOIN `pedidos` (filtered by dias, exclude cancelado)
  - Query 2: Products grouped from `pedido_items` JOIN `pedidos` (filtered by dias, exclude cancelado)
  - Map results to `InsightConsolidadoDTO`
- [ ] Implement `get_pedidos(db, cliente_id, empresa_id, dias)`:
  - Query: Recent pedidos ordered by date desc, filtered by dias and empresa_id, LIMIT 100
  - Map results to `InsightPedidosDTO`
- [ ] All SQL uses `sqlalchemy.text` with binded params (`:param`)
- [ ] `empresa_id` used in every WHERE clause for multi-tenant isolation

## Phase 4: Router

### 4.1 Create clientes router with auth
- [ ] Create `app/api/routers/clientes.py`
- [ ] Implement `GET /api/clientes/{cliente_id}/insights`
  - Parameters: `type` (Query, required, consolidado|pedidos), `dias` (Query, default=30, ge=1, le=365)
  - Auth: `Depends(get_current_user)`
  - DB: `Depends(get_db)`
  - Validate cliente belongs to user's empresa (404 if not)
  - Dispatch to service based on `type`
  - Return HTMX partial: `partials/cliente_insights.html`

### 4.2 Register router in main app
- [ ] Modify `app/main.py` to include `clientes_router`
- [ ] Verify CSRF exemption for GET endpoint

## Phase 5: Frontend (HTMX Partial)

### 5.1 Create cliente insights partial
- [ ] Create `app/templates/partials/cliente_insights.html`
- [ ] Implement tabs: [Consolidado] [Pedidos] with `hx-get` switching
- [ ] Implement dias selector: [7d] [15d] [30d] [60d] [90d] [TODO]
- [ ] Render `Consolidado` view:
  - Header: nombre, apellido, celular
  - Saldo pendiente (TOTAL debt, red if > 0, green if 0)
  - Límite de crédito (if set)
  - Separator: "Últimos {dias} días"
  - Stats row: total_pedidos, total_vendido, total_senia
  - Products table: descripcion, cantidad, monto, ultima_compra
  - Empty state message if no data
- [ ] Render `Pedidos` view:
  - Header: nombre, apellido
  - List of pedidos with estado badge (color-coded)
  - Empty state message if no data
- [ ] Tailwind CSS styling matching existing app theme

### 5.2 Integrate insights into existing UI
- [ ] Modify client search results (`partials/clientes_resultado.html`) or buscar page to add insight trigger
- [ ] Option: Add "📊 Insights" link/button on each client in search results that loads the partial via HTMX

## Phase 6: Testing

### 6.1 Write tests for query service
- [ ] Test `get_consolidado` returns correct aggregated data
- [ ] Test `get_consolidado` with no pedidos returns zeros
- [ ] Test `get_pedidos` returns ordered pedidos
- [ ] Test multi-tenant isolation (empresa A can't see empresa B's data)
- [ ] Test `dias` parameter validation

### 6.2 Write tests for router
- [ ] Test GET /api/clientes/{id}/insights?type=consolidado returns 200
- [ ] Test GET /api/clientes/{id}/insights?type=pedidos returns 200
- [ ] Test 404 for client from different empresa
- [ ] Test 422 for invalid type or dias params
- [ ] Test 401 for unauthenticated requests
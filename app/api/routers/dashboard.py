import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Pago, Pedido, Usuario
from app.repositories import cliente_repo, pedido_repo, producto_repo
from app.services import pedido_service
from app.templates_env import get_templates

logger = logging.getLogger(__name__)

router = APIRouter()
templates = get_templates()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    logger.info("Dashboard accessed by user_id=%s (empresa_id=%s)", current_user.id, current_user.empresa_id)

    hoy: date = datetime.now(UTC).date()

    # KPIs: una sola query para pedidos del mes (solo campos numéricos, sin items)
    pedidos_mes = await pedido_service.get_pedidos_mes(db, current_user.empresa_id)
    total_ventas, cantidad_pedidos = pedido_service.calcular_kpis_mes(pedidos_mes)

    # Top 5 productos: una sola query SQL con GROUP BY (sin cargar todos los pedidos)
    top_productos = await pedido_repo.get_top_productos_mes(db, current_user.empresa_id, limit=5)

    # Conteos por estado (en memoria, ya tenemos los pedidos)
    pendientes = sum(1 for p in pedidos_mes if p.estado == "pendiente")
    entregados = sum(1 for p in pedidos_mes if p.estado == "entregado")

    # Stock bajo
    stock_bajo_count = await producto_repo.count_stock_bajo(db, current_user.empresa_id)

    # Top deudores
    top_deudores = await cliente_repo.get_top_deudores(db, current_user.empresa_id, limit=5)
    total_deuda = sum(float(c.saldo_pendiente or 0) for c in top_deudores)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": current_user,
            "total_ventas": total_ventas,
            "cantidad_pedidos": cantidad_pedidos,
            "top_productos": top_productos,
            "pendientes": pendientes,
            "entregados": entregados,
            "mes_actual": hoy.strftime("%B %Y"),
            "stock_bajo_count": stock_bajo_count,
            "top_deudores": top_deudores,
            "total_deuda": total_deuda,
        },
    )


@router.get("/stock-bajo", response_class=HTMLResponse)
async def stock_bajo_page(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Vista de productos con stock por debajo del mínimo."""
    productos = await producto_repo.get_stock_bajo(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "stock_bajo.html",
        {
            "user": current_user,
            "productos": productos,
        },
    )


@router.get("/api/clientes/{cliente_id}/cuenta-corriente", response_class=HTMLResponse)
async def cuenta_corriente_detalle(
    cliente_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Devuelve el detalle de cuenta corriente de un cliente (HTMX partial).

    Muestra pedidos con saldo pendiente, historial de pagos y formulario
    para registrar nuevos pagos.
    """
    cliente = await cliente_repo.get_by_id(db, cliente_id, current_user.empresa_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    # Pedidos del cliente con saldo pendiente (no cancelados)
    pedidos_query = (
        select(Pedido)
        .where(
            Pedido.cliente_id == cliente_id,
            Pedido.empresa_id == current_user.empresa_id,
            Pedido.estado != "cancelado",
        )
        .order_by(Pedido.fecha_creacion.desc())
    )
    pedidos_result = await db.execute(pedidos_query)
    pedidos = list(pedidos_result.scalars().all())

    # Historial de pagos
    pagos = await cliente_repo.get_pagos_cliente(db, cliente_id, current_user.empresa_id)

    # Calcular totales para el tfooter
    total_pedidos = sum(float(p.total or 0) for p in pedidos)
    total_senias = sum(float(p.senia or 0) for p in pedidos)
    total_saldo = total_pedidos - total_senias

    return templates.TemplateResponse(
        request,
        "partials/cuenta_corriente_detalle.html",
        {
            "user": current_user,
            "cliente": cliente,
            "pedidos": pedidos,
            "pagos": pagos,
            "total_pedidos": total_pedidos,
            "total_senias": total_senias,
            "total_saldo": total_saldo,
        },
    )


@router.post("/api/clientes/{cliente_id}/registrar-pago-htmx", response_class=HTMLResponse)
async def registrar_pago_htmx(
    cliente_id: int,
    request: Request,
    monto: float = Form(...),
    metodo_pago: str = Form("efectivo"),
    nota: str = Form(""),
    pedido_id: str = Form(""),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Registra un pago y devuelve el partial actualizado de cuenta corriente."""
    if monto <= 0:
        return templates.TemplateResponse(
            request,
            "partials/error.html",
            {"error": "El monto debe ser mayor a 0"},
        )

    pid = int(pedido_id) if pedido_id else None

    try:
        pago, cliente = await cliente_repo.registrar_pago(
            db,
            cliente_id=cliente_id,
            empresa_id=current_user.empresa_id,
            monto=Decimal(str(monto)),
            usuario_id=current_user.id,
            pedido_id=pid,
            metodo_pago=metodo_pago,
            nota=nota or None,
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "partials/error.html",
            {"error": str(e)},
        )

    logger.info(
        "Pago $%s registrado para cliente #%s por usuario #%s",
        monto, cliente_id, current_user.id,
    )

    # Recargar datos para el partial actualizado
    pedidos_query = (
        select(Pedido)
        .where(
            Pedido.cliente_id == cliente_id,
            Pedido.empresa_id == current_user.empresa_id,
            Pedido.estado != "cancelado",
        )
        .order_by(Pedido.fecha_creacion.desc())
    )
    pedidos_result = await db.execute(pedidos_query)
    pedidos = list(pedidos_result.scalars().all())

    pagos = await cliente_repo.get_pagos_cliente(db, cliente_id, current_user.empresa_id)

    # Refetch cliente para saldo actualizado
    cliente = await cliente_repo.get_by_id(db, cliente_id, current_user.empresa_id)

    # Calcular totales para el tfooter
    total_pedidos = sum(float(p.total or 0) for p in pedidos)
    total_senias = sum(float(p.senia or 0) for p in pedidos)
    total_saldo = total_pedidos - total_senias

    # OOB: datos frescos de deudores para actualizar la tabla
    top_deudores = await cliente_repo.get_top_deudores(db, current_user.empresa_id, limit=5)
    total_deuda = sum(float(c.saldo_pendiente or 0) for c in top_deudores)

    return templates.TemplateResponse(
        request,
        "partials/cuenta_corriente_detalle.html",
        {
            "user": current_user,
            "cliente": cliente,
            "pedidos": pedidos,
            "pagos": pagos,
            "pago_exitoso": True,
            "pago_monto": monto,
            "total_pedidos": total_pedidos,
            "total_senias": total_senias,
            "total_saldo": total_saldo,
            "top_deudores": top_deudores,
            "total_deuda": total_deuda,
        },
    )

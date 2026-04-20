import logging
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Usuario
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
    hoy: date = datetime.now(UTC).date()
    pedidos_mes = await pedido_service.get_pedidos_mes(db, current_user.empresa_id)

    total_ventas, cantidad_pedidos = pedido_service.calcular_kpis_mes(pedidos_mes)
    top_productos = pedido_service.calcular_top_productos(pedidos_mes)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": current_user,
            "total_ventas": total_ventas,
            "cantidad_pedidos": cantidad_pedidos,
            "top_productos": top_productos,
            "pendientes": sum(1 for p in pedidos_mes if p.estado == "pendiente"),
            "entregados": sum(1 for p in pedidos_mes if p.estado == "entregado"),
            "mes_actual": hoy.strftime("%B %Y"),
        },
    )

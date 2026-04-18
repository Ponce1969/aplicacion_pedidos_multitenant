from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Pedido, Usuario

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    hoy: date = datetime.now(UTC).date()
    primer_dia_mes: date = hoy.replace(day=1)

    query = select(Pedido).where(Pedido.fecha_creacion >= primer_dia_mes).order_by(Pedido.fecha_creacion.desc())

    result = await db.execute(query)
    pedidos_mes: list[Pedido] = list(result.scalars().all())

    total_ventas: float = sum(pedido.total for pedido in pedidos_mes)
    cantidad_pedidos: int = len(pedidos_mes)

    # Productos más vendidos — parseo del campo pedido_detalle
    productos_vendidos: dict[str, float] = {}
    for pedido in pedidos_mes:
        try:
            lineas: list[str] = pedido.pedido_detalle.split("\n")
            for linea in lineas:
                if "-" in linea:
                    partes: list[str] = linea.split("-", 1)
                    nombre_prod: str = partes[0].strip()
                    try:
                        cantidad_str: str = partes[1].strip().replace("kg", "").replace("unidad", "").strip()
                        cantidad: float = float(cantidad_str)
                    except (ValueError, IndexError):
                        cantidad = 1.0
                    productos_vendidos[nombre_prod] = productos_vendidos.get(nombre_prod, 0.0) + cantidad
        except (AttributeError, ValueError):
            pass

    top_productos: list[tuple[str, float]] = sorted(productos_vendidos.items(), key=lambda x: x[1], reverse=True)[:5]

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "user": current_user,
            "total_ventas": total_ventas,
            "cantidad_pedidos": cantidad_pedidos,
            "top_productos": top_productos,
            "pedidos_recientes": pedidos_mes[:10],
            "mes_actual": hoy.strftime("%B %Y"),
        },
    )

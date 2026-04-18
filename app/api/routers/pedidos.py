from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Pedido, Usuario
from app.services import pedido_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/nuevo-pedido", response_class=HTMLResponse)
async def nuevo_pedido_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "nuevo_pedido.html",
        {
            "user": current_user,
        },
    )


@router.post("/guardar-pedido")
async def guardar_pedido(  # noqa: PLR0913 — too many args
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    celular: str = Form(...),
    direccion: str = Form(...),
    hora_entrega: str = Form(...),
    fecha_entrega: str = Form(...),
    pedido_detalle: str = Form(...),
    total: float = Form(...),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    # Convertir fecha string a datetime con timezone
    fecha_dt: datetime = datetime.strptime(fecha_entrega, "%Y-%m-%d")
    fecha_dt = fecha_dt.replace(tzinfo=UTC)

    nuevo_pedido = Pedido(
        usuario_id=current_user.id,
        nombre=nombre,
        apellido=apellido,
        celular=celular,
        direccion=direccion,
        hora_entrega=hora_entrega,
        fecha_entrega=fecha_dt,
        pedido_detalle=pedido_detalle,
        total=total,
    )

    saved = await pedido_service.crear_pedido(db, nuevo_pedido)

    return templates.TemplateResponse(
        request, "partials/success.html", {"mensaje": f"✅ Pedido #{saved.id} guardado exitosamente"},
    )


@router.get("/buscar", response_class=HTMLResponse)
async def buscar_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "buscar.html",
        {
            "user": current_user,
        },
    )


@router.post("/buscar-pedidos")
async def buscar_pedidos(
    request: Request,
    termino: str = Form(...),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedidos = await pedido_service.buscar_pedidos(db, termino)

    return templates.TemplateResponse(
        request, "partials/resultados_busqueda.html", {"pedidos": pedidos, "termino": termino},
    )


@router.get("/pedido/{pedido_id}")
async def ver_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedido = await pedido_service.get_pedido(db, pedido_id)

    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    return templates.TemplateResponse(
        request, "partials/detalle_pedido.html", {"pedido": pedido, "user": current_user},
    )

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Pedido, Usuario
from app.repositories import cliente_repo, producto_repo
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


# --- HTMX: Buscar clientes (autocompletado) ---


@router.get("/api/clientes/buscar")
async def buscar_clientes(
    request: Request,
    q: str = "",
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if len(q) < 2:
        return HTMLResponse("")

    clientes = await cliente_repo.search(db, q, current_user.empresa_id)
    return templates.TemplateResponse(
        request, "partials/clientes_resultado.html", {"clientes": clientes},
    )


# --- HTMX: Buscar productos (autocompletado) ---


@router.get("/api/productos/buscar")
async def buscar_productos(
    request: Request,
    q: str = "",
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if len(q) < 2:
        return HTMLResponse("")

    productos = await producto_repo.search(db, q, current_user.empresa_id)
    return templates.TemplateResponse(
        request, "partials/productos_resultado.html", {"productos": productos},
    )


# --- Guardar pedido (soporta items JSON) ---


@router.post("/guardar-pedido")
async def guardar_pedido(  # noqa: PLR0913 — too many args
    request: Request,
    nombre: str = Form(""),
    apellido: str = Form(""),
    celular: str = Form(""),
    direccion: str = Form(""),
    hora_entrega: str = Form(""),
    fecha_entrega: str = Form(""),
    pedido_detalle: str = Form(""),
    total: float = Form(0.0),
    cliente_id: str = Form(""),
    items_json: str = Form("[]"),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    # Convertir fecha string a datetime con timezone
    fecha_dt: datetime | None = None
    if fecha_entrega:
        fecha_dt = datetime.strptime(fecha_entrega, "%Y-%m-%d").replace(tzinfo=UTC)

    # Resolver cliente_id
    cid: int | None = int(cliente_id) if cliente_id else None

    # Si hay items JSON, usar el nuevo flujo
    items: list[dict] = json.loads(items_json) if items_json else []

    if items:
        nuevo_pedido = Pedido(
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
            cliente_id=cid,
            nombre=nombre,
            apellido=apellido,
            celular=celular,
            direccion=direccion,
            hora_entrega=hora_entrega,
            fecha_entrega=fecha_dt,
            pedido_detalle=pedido_detalle,
        )
        saved = await pedido_service.crear_pedido_con_items(db, nuevo_pedido, items)
    else:
        # Flujo legacy (sin items)
        nuevo_pedido = Pedido(
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
            cliente_id=cid,
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
    pedidos = await pedido_service.buscar_pedidos(db, termino, current_user.empresa_id)

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

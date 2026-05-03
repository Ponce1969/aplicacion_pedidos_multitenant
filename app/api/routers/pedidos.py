import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Pedido, Usuario
from app.repositories import cliente_repo, producto_repo, entrega_repo
from app.repositories.producto_repo import InsufficientStockError
from app.services import pedido_service
from app.services.pedido_service import InvalidEstadoTransition
from app.templates_env import get_templates

logger = logging.getLogger(__name__)

VALID_ESTADOS = {"pendiente", "entregado", "cancelado"}

router = APIRouter()
templates = get_templates()


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> RedirectResponse:
    return RedirectResponse(url="/pedidos", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/nuevo-pedido", response_class=HTMLResponse)
async def nuevo_pedido_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "nuevo_pedido.html",
        {
            "user": current_user,
        },
    )


@router.get("/pedidos", response_class=HTMLResponse)
async def pedidos_page(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedidos = await pedido_service.get_pedidos_mes(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "pedidos.html",
        {"user": current_user, "pedidos": pedidos},
    )


@router.get("/entregas", response_class=HTMLResponse)
async def entregas_page(
    request: Request,
    fecha: str | None = None,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    fecha_filtro: date | None = None
    if fecha:
        fecha_filtro = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=UTC).date()

    pedidos = await pedido_service.get_pedidos_pendientes(db, current_user.empresa_id, fecha_filtro)
    hoy = datetime.now(UTC).strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        request,
        "entregas.html",
        {
            "user": current_user,
            "pedidos": pedidos,
            "fecha": fecha or hoy,
            "hoy": hoy,
        },
    )


@router.post("/api/pedido/{pedido_id}/marcar-entregado")
async def marcar_entregado(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    pedido.estado = "entregado"
    await db.commit()

    return HTMLResponse(content="", status_code=status.HTTP_200_OK, headers={"HX-Trigger": "pedidoEntregado"})


@router.post("/api/pedido/{pedido_id}/cancelar")
async def cancelar_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Cancela un pedido y restaura el stock de cada producto."""
    pedido = await pedido_service.cancelar_pedido(db, pedido_id, current_user.empresa_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    logger.info(
        "Pedido #%s cancelado por usuario #%s (empresa %s) — stock restaurado",
        pedido_id,
        current_user.id,
        current_user.empresa_id,
    )

    return HTMLResponse(content="", status_code=status.HTTP_200_OK, headers={"HX-Trigger": "pedidoCancelado"})


@router.delete("/api/pedido/{pedido_id}")
async def eliminar_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    deleted = await pedido_service.delete_pedido(db, pedido_id, current_user.empresa_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    logger.info(
        "Pedido #%s eliminado por usuario #%s (empresa %s)",
        pedido_id,
        current_user.id,
        current_user.empresa_id,
    )

    return HTMLResponse(content="", status_code=status.HTTP_200_OK, headers={"HX-Redirect": "/buscar"})


@router.get("/editar-pedido/{pedido_id}", response_class=HTMLResponse)
async def editar_pedido_form(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    return templates.TemplateResponse(
        request,
        "editar_pedido.html",
        {"user": current_user, "pedido": pedido},
    )


@router.post("/editar-pedido/{pedido_id}")
async def editar_pedido_guardar(  # noqa: PLR0913
    pedido_id: int,
    request: Request,
    nombre: str = Form(""),
    apellido: str = Form(""),
    celular: str = Form(""),
    direccion: str = Form(""),
    hora_entrega: str = Form(""),
    fecha_entrega: str = Form(""),
    pedido_detalle: str = Form(""),
    estado: str = Form("pendiente"),
    senia: float = Form(0.0),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if estado not in VALID_ESTADOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado inválido. Valores permitidos: {', '.join(sorted(VALID_ESTADOS))}",
        )

    fecha_dt: datetime | None = None
    if fecha_entrega:
        fecha_dt = datetime.strptime(fecha_entrega, "%Y-%m-%d").replace(tzinfo=UTC)
    
    # Calcular estado de pago basado en seña vs total
    senia_decimal = Decimal(str(senia)) if senia else Decimal("0")
    
    # Obtener el pedido actual para saber el total
    pedido_actual = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)
    if pedido_actual is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    
    total_decimal = Decimal(str(pedido_actual.total)) if pedido_actual.total else Decimal("0")
    
    if senia_decimal >= total_decimal and total_decimal > 0:
        estado_pago = "pagado"
    elif senia_decimal > 0:
        estado_pago = "parcial"
    else:
        estado_pago = "pendiente"

    datos = {
        "nombre": nombre,
        "apellido": apellido,
        "celular": celular,
        "direccion": direccion,
        "hora_entrega": hora_entrega,
        "fecha_entrega": fecha_dt,
        "pedido_detalle": pedido_detalle,
        "estado": estado,
        "senia": senia_decimal,
        "estado_pago": estado_pago,
    }

    # Si se está cancelando el pedido, restaurar stock
    if estado == "cancelado" and pedido_actual.estado != "cancelado":
        pedido = await pedido_service.cancelar_pedido(db, pedido_id, current_user.empresa_id)
        if pedido is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    else:
        pedido = await pedido_service.update_pedido(db, pedido_id, current_user.empresa_id, datos)
        if pedido is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    logger.info(
        "Pedido #%s actualizado por usuario #%s (empresa %s): estado=%s, estado_pago=%s, senia=%s",
        pedido.id,
        current_user.id,
        current_user.empresa_id,
        estado,
        estado_pago,
        senia_decimal,
    )

    return templates.TemplateResponse(
        request,
        "partials/success.html",
        {"mensaje": f"Pedido #{pedido.id} actualizado correctamente"},
    )


# --- HTMX: Buscar clientes (autocompletado) ---


@router.get("/api/clientes/buscar")
async def buscar_clientes(
    request: Request,
    q: str = "",
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if len(q) < 2:  # noqa: PLR2004 — min search chars
        return HTMLResponse("")

    clientes = await cliente_repo.search(db, q, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "partials/clientes_resultado.html",
        {"clientes": clientes},
    )


@router.get("/api/clientes/{cliente_id}/direcciones")
async def get_direcciones_cliente(
    cliente_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """HTMX: Retorna las direcciones de un cliente como options para un select."""
    direcciones = await cliente_repo.get_direcciones(db, cliente_id, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "partials/direcciones_select.html",
        {"direcciones": direcciones},
    )


# --- Cuenta Corriente: Registrar Pago ---


@router.post("/api/clientes/{cliente_id}/registrar-pago")
async def registrar_pago(
    cliente_id: int,
    request: Request,
    monto: float = Form(...),
    metodo_pago: str = Form("efectivo"),
    nota: str = Form(""),
    pedido_id: str = Form(""),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Registra un pago de un cliente y reduce su saldo pendiente."""
    from decimal import Decimal as D

    if monto <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El monto debe ser mayor a 0",
        )

    pid = int(pedido_id) if pedido_id else None

    try:
        pago, cliente = await cliente_repo.registrar_pago(
            db,
            cliente_id=cliente_id,
            empresa_id=current_user.empresa_id,
            monto=D(str(monto)),
            usuario_id=current_user.id,
            pedido_id=pid,
            metodo_pago=metodo_pago,
            nota=nota or None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    logger.info(
        "Pago $%s registrado para cliente #%s por usuario #%s (empresa %s)",
        monto,
        cliente_id,
        current_user.id,
        current_user.empresa_id,
    )

    return templates.TemplateResponse(
        request,
        "partials/success.html",
        {"mensaje": f"✅ Pago de ${monto:.0f} registrado. Saldo pendiente: ${float(cliente.saldo_pendiente):.0f}"},
    )


@router.get("/api/clientes/{cliente_id}/saldo")
async def get_saldo_cliente(
    cliente_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """HTMX: Retorna el saldo pendiente de un cliente."""
    from fastapi.responses import JSONResponse

    cliente = await cliente_repo.get_by_id(db, cliente_id)
    if cliente is None or cliente.empresa_id != current_user.empresa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    return JSONResponse(content={
        "saldo_pendiente": float(cliente.saldo_pendiente or 0),
        "limite_credito": float(cliente.limite_credito) if cliente.limite_credito else None,
    })


# --- HTMX: Buscar productos (autocompletado) ---


@router.get("/api/productos/buscar")
async def buscar_productos(
    request: Request,
    q: str = "",
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if len(q) < 2:  # noqa: PLR2004 — min search chars
        return HTMLResponse("")

    productos = await producto_repo.search(db, q, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "partials/productos_resultado.html",
        {"productos": productos},
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
    senia: float = Form(0.0),
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

    # Calcular estado de pago basado en seña vs total
    senia_decimal = Decimal(str(senia)) if senia else Decimal("0")
    total_decimal = Decimal(str(total)) if total else Decimal("0")
    
    if senia_decimal >= total_decimal and total_decimal > 0:
        estado_pago = "pagado"
    elif senia_decimal > 0:
        estado_pago = "parcial"
    else:
        estado_pago = "pendiente"

    # Si hay items JSON, usar el nuevo flujo
    items: list[dict[str, float | int | str]] = json.loads(items_json) if items_json else []

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
            senia=senia_decimal,
            estado_pago=estado_pago,
        )
        try:
            saved = await pedido_service.crear_pedido_con_items(db, nuevo_pedido, items)
        except InsufficientStockError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
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
            senia=senia_decimal,
            estado_pago=estado_pago,
        )
        saved = await pedido_service.crear_pedido(db, nuevo_pedido)

    return templates.TemplateResponse(
        request,
        "partials/success.html",
        {"mensaje": f"✅ Pedido #{saved.id} guardado exitosamente"},
    )


@router.get("/buscar", response_class=HTMLResponse)
async def buscar_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "buscar.html",
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
        request,
        "partials/resultados_busqueda.html",
        {"pedidos": pedidos, "termino": termino},
    )


@router.get("/pedido/{pedido_id}")
async def ver_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)

    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    return templates.TemplateResponse(
        request,
        "partials/detalle_pedido.html",
        {"pedido": pedido, "user": current_user},
    )


@router.get("/pedido/{pedido_id}/imprimir")
async def imprimir_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Genera vista optimizada para imprimir el pedido.

    El repartidor recibe este papel con los detalles de entrega.
    Incluye espacio para firma de confirmación.
    """
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)

    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    return templates.TemplateResponse(
        request,
        "imprimir_pedido.html",
        {"pedido": pedido, "user": current_user},
    )


@router.get("/pedido/{pedido_id}/descargar")
async def descargar_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Descarga el pedido como archivo HTML para imprimir."""
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)

    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    response = templates.TemplateResponse(
        request,
        "imprimir_pedido.html",
        {"pedido": pedido, "user": current_user},
    )

    filename = (
        f"pedido-{pedido.id}-{pedido.fecha_creacion.strftime('%Y%m%d') if pedido.fecha_creacion else 'draft'}.html"
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ==================== M-02: REPARTIDORES ====================


@router.get("/mis-entregas", response_class=HTMLResponse)
async def mis_entregas(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Vista del repartidor: pedidos asignados del día."""
    pedidos = await pedido_service.get_pedidos_asignados_repartidor(
        db, current_user.id, current_user.empresa_id
    )
    return templates.TemplateResponse(
        request,
        "entregas.html",
        {
            "user": current_user,
            "pedidos": pedidos,
            "fecha": datetime.now(UTC).strftime("%Y-%m-%d"),
            "hoy": datetime.now(UTC).strftime("%Y-%m-%d"),
            "es_repartidor": True,
        },
    )


@router.post("/api/pedido/{pedido_id}/asignar-repartidor")
async def asignar_repartidor(
    pedido_id: int,
    request: Request,
    repartidor_id: int = Form(...),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Admin asigna un repartidor a un pedido."""
    # Verificar que el repartidor exista y sea de la misma empresa
    from app.repositories import usuario_repo

    repartidor = await usuario_repo.get_by_id(db, repartidor_id, current_user.empresa_id)
    if repartidor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repartidor no encontrado")

    if repartidor.rol not in ("repartidor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario asignado debe tener rol 'repartidor' o 'admin'",
        )

    pedido = await pedido_service.asignar_repartidor(
        db, pedido_id, repartidor_id, current_user.id, current_user.empresa_id
    )
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    logger.info(
        "Repartidor #%s asignado a pedido #%s por usuario #%s",
        repartidor_id,
        pedido_id,
        current_user.id,
    )

    return HTMLResponse(content="", status_code=status.HTTP_200_OK, headers={"HX-Trigger": "repartidorAsignado"})


@router.post("/api/pedido/{pedido_id}/cambiar-estado")
async def cambiar_estado_pedido(
    pedido_id: int,
    request: Request,
    nuevo_estado: str = Form(...),
    nota: str = Form(""),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Cambia el estado de un pedido con validación de transiciones."""
    try:
        pedido = await pedido_service.cambiar_estado_entrega(
            db, pedido_id, nuevo_estado, current_user.id, current_user.empresa_id, nota or None
        )
    except InvalidEstadoTransition as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    logger.info(
        "Pedido #%s: estado cambiado a '%s' por usuario #%s",
        pedido_id,
        nuevo_estado,
        current_user.id,
    )

    return HTMLResponse(content="", status_code=status.HTTP_200_OK, headers={"HX-Trigger": "estadoCambiado"})


@router.get("/api/pedido/{pedido_id}/historial")
async def historial_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    """Obtiene el historial de eventos de un pedido."""
    pedido = await pedido_service.get_pedido_by_id(db, pedido_id, current_user.empresa_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    eventos = await entrega_repo.get_by_pedido(db, pedido_id)

    # Retornar JSON para API
    from fastapi.responses import JSONResponse

    eventos_data = [
        {
            "id": e.id,
            "estado_anterior": e.estado_anterior,
            "estado_nuevo": e.estado_nuevo,
            "nota": e.nota,
            "usuario_id": e.usuario_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in eventos
    ]
    return JSONResponse(content=eventos_data)

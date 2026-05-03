"""Router para gestión de configuración de empresa.

Solo admins pueden acceder.
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin_user
from app.database import get_db
from app.models import Usuario
from app.services import configuracion_service
from app.templates_env import get_templates


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/configuracion", tags=["admin"])
templates = get_templates()


@router.get("/", response_class=HTMLResponse)
async def configuracion_page(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Página de configuración de la empresa (solo admins)."""
    config = await configuracion_service.get_configuracion(db, current_user.empresa_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return templates.TemplateResponse(
        request,
        "configuracion/index.html",
        {"user": current_user, "config": config},
    )


@router.post("/actualizar")
async def actualizar_configuracion(
    request: Request,
    nombre: str = Form(...),
    rubro: str = Form(""),
    email_contacto: str = Form(""),
    telefono_contacto: str = Form(""),
    logo_url: str = Form(""),
    color_primario: str = Form("#3b82f6"),
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Actualiza la configuración de la empresa."""
    if not nombre or len(nombre.strip()) < 2:
        config = await configuracion_service.get_configuracion(db, current_user.empresa_id)
        return templates.TemplateResponse(
            request,
            "configuracion/index.html",
            {
                "user": current_user,
                "config": config or {},
                "error": "El nombre debe tener al menos 2 caracteres",
            },
        )

    try:
        config = await configuracion_service.actualizar_configuracion(
            db,
            current_user.empresa_id,
            nombre=nombre,
            rubro=rubro,
            email_contacto=email_contacto,
            telefono_contacto=telefono_contacto,
            logo_url=logo_url,
            color_primario=color_primario,
        )
        logger.info(
            "Configuracion actualizada por usuario %s (empresa %s)",
            current_user.id,
            current_user.empresa_id,
        )
        return templates.TemplateResponse(
            request,
            "configuracion/index.html",
            {"user": current_user, "config": config, "success": "Configuración guardada correctamente"},
        )
    except Exception as e:
        logger.error("Error al actualizar configuracion: %s", e)
        config = await configuracion_service.get_configuracion(db, current_user.empresa_id)
        return templates.TemplateResponse(
            request,
            "configuracion/index.html",
            {
                "user": current_user,
                "config": config or {},
                "error": f"Error al guardar: {str(e)}",
            },
        )


@router.get("/api/config")
async def obtener_config_api(
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """API endpoint para obtener config como JSON (para dynamic CSS)."""
    from fastapi.responses import JSONResponse

    config = await configuracion_service.get_configuracion(db, current_user.empresa_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return JSONResponse(content=config)
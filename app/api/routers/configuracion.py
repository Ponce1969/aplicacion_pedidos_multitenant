"""Router para configuración de empresa — endpoints legacy redirigidos al panel admin.

Mantiene únicamente el endpoint JSON para CSS dinámico.
La vista HTML de configuración ahora vive en /admin (tab Empresa).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin_user
from app.database import get_db
from app.models import Usuario
from app.services import configuracion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/configuracion", tags=["admin"])


@router.get("/api/config")
async def obtener_config_api(
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """API endpoint para obtener config como JSON (para dynamic CSS)."""
    config = await configuracion_service.get_configuracion(db, current_user.empresa_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return JSONResponse(content=config)
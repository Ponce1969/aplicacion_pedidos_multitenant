"""Router público para onboarding de nuevas empresas.

Este router NO requiere autenticación. Es la puerta de entrada para nuevos clientes.
"""

import logging
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limiter import onboarding_limiter
from app.services import onboarding_service


router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

logger = logging.getLogger(__name__)


class RegistroRequest(BaseModel):
    """Request body para registro de nueva empresa."""

    nombre_empresa: str
    email_admin: str
    nombre_admin: str
    apellido_admin: str
    password: str

    @field_validator("nombre_empresa")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        if re.match(r"^\d+$", v.strip()):
            raise ValueError("El nombre no puede ser solo números")
        return v.strip()

    @field_validator("email_admin")
    @classmethod
    def validar_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("nombre_admin", "apellido_admin")
    @classmethod
    def validar_nombre_admin(cls, v: str) -> str:
        if not v or len(v.strip()) < 1:
            raise ValueError("El nombre y apellido son obligatorios")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("La contraseña debe tener al menos una mayúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe tener al menos un número")
        return v


class RegistroResponse(BaseModel):
    """Response para registro exitoso."""

    empresa_id: int
    empresa_nombre: str
    empresa_slug: str
    admin_id: int
    admin_email: str
    cliente_default_id: int
    message: str


@router.post("/register", response_model=RegistroResponse)
async def registrar_empresa(
    request: Request,
    registro: RegistroRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Registra una nueva empresa con su admin y cliente default.

    Rate limited: 3 requests por IP cada 10 minutos.
    Transacción atómica: si algo falla, rollback completo.

    Args:
        registro: Datos del registro validado.

    Returns:
        JSON con datos de la empresa creada.

    Raises:
        400: Validación fallida (nombre muy corto, email existente, password débil).
        429: Rate limit excedido.
    """
    # Verificar rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not onboarding_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de registro. Esperá 10 minutos antes de intentar de nuevo.",
        )

    try:
        empresa, admin, cliente_default = await onboarding_service.crear_empresa_y_admin(
            db,
            nombre_empresa=registro.nombre_empresa,
            email_admin=registro.email_admin,
            nombre_admin=registro.nombre_admin,
            apellido_admin=registro.apellido_admin,
            password=registro.password,
        )

        return {
                "empresa_id": empresa.id,
                "empresa_nombre": empresa.nombre,
                "empresa_slug": empresa.slug,
                "admin_id": admin.id,
                "admin_email": admin.email,
                "cliente_default_id": cliente_default.id,
                "message": "Empresa registrada exitosamente",
            }

    except onboarding_service.EmailYaRegistradoError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado en otra empresa",
        )
    except onboarding_service.NombreEmpresaInvalidoError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de empresa debe tener al menos 3 caracteres y no puede ser solo números",
        )
    except onboarding_service.SlugNoDisponibleError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de empresa no está disponible",
        )
    except Exception as e:
        # Cualquier error inesperado hace rollback
        await db.rollback()
        logger.error("Onboarding error: %s - %s", type(e).__name__, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}",
        )
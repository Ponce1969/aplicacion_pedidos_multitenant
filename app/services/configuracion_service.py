"""Servicio para gestionar configuración de empresa.

Maneja lectura y actualización de los campos editables de Empresa.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Empresa
from app.repositories import empresa_repo


class ConfiguracionError(Exception):
    """Error general de configuración."""


async def get_configuracion(db: AsyncSession, empresa_id: int) -> dict | None:
    """Obtiene la configuración de una empresa.

    Returns dict con: nombre, logo_url, color_primario, email_contacto, telefono_contacto
    o None si la empresa no existe.
    """
    empresa = await empresa_repo.get_by_id(db, empresa_id)
    if empresa is None:
        return None

    return {
        "nombre": empresa.nombre,
        "logo_url": empresa.logo_url,
        "color_primario": empresa.color_primario,
        "email_contacto": empresa.email_contacto,
        "telefono_contacto": empresa.telefono_contacto,
        "rubro": empresa.rubro,
        "moneda": empresa.moneda,
    }


async def actualizar_configuracion(
    db: AsyncSession,
    empresa_id: int,
    *,
    nombre: str | None = None,
    logo_url: str | None = None,
    color_primario: str | None = None,
    email_contacto: str | None = None,
    telefono_contacto: str | None = None,
    rubro: str | None = None,
) -> dict:
    """Actualiza campos editables de una empresa.

    Todos los parámetros son opcionales. Solo actualiza los que no son None.

    Returns dict con la config actualizada.

    Raises:
        ConfiguracionError: Si la empresa no existe.
    """
    empresa = await empresa_repo.get_by_id(db, empresa_id)
    if empresa is None:
        raise ConfiguracionError("Empresa no encontrada")

    if nombre is not None:
        empresa.nombre = nombre.strip()
    if logo_url is not None:
        empresa.logo_url = logo_url.strip() or None
    if color_primario is not None:
        empresa.color_primario = color_primario.strip() or "#3b82f6"
    if email_contacto is not None:
        empresa.email_contacto = email_contacto.strip() or None
    if telefono_contacto is not None:
        empresa.telefono_contacto = telefono_contacto.strip() or None
    if rubro is not None:
        empresa.rubro = rubro.strip() or None

    await db.commit()
    await db.refresh(empresa)

    return {
        "nombre": empresa.nombre,
        "logo_url": empresa.logo_url,
        "color_primario": empresa.color_primario,
        "email_contacto": empresa.email_contacto,
        "telefono_contacto": empresa.telefono_contacto,
        "rubro": empresa.rubro,
        "moneda": empresa.moneda,
    }
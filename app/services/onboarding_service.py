"""Servicio de onboarding para registro de nuevas empresas.

Maneja la creación atómica de empresa + admin + cliente seed.
Si algo falla en el camino, hace rollback completo.
"""

import logging
import re
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.auth import get_password_hash
from app.models import Cliente, Empresa, Usuario
from app.repositories import empresa_repo, usuario_repo, cliente_repo
from app.utils import generar_slug


class OnboardingError(Exception):
    """Error durante el proceso de onboarding."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)


class EmailYaRegistradoError(OnboardingError):
    """El email ya está registrado en otra empresa."""

    def __init__(self) -> None:
        super().__init__("El email ya está registrado", field="email")


class SlugNoDisponibleError(OnboardingError):
    """El slug generado ya existe en la base de datos."""

    def __init__(self) -> None:
        super().__init__("El nombre de empresa no está disponible", field="nombre")


class NombreEmpresaInvalidoError(OnboardingError):
    """El nombre de empresa no cumple con las reglas de negocio."""

    def __init__(self) -> None:
        super().__init__(
            "El nombre de empresa debe tener al menos 3 caracteres y no puede ser solo números",
            field="nombre",
        )


def validar_nombre_empresa(nombre: str) -> None:
    """Valida que el nombre de empresa cumpla con las reglas de negocio.

    Raises:
        NombreEmpresaInvalidoError: Si el nombre es muy corto o solo números.
    """
    if not nombre or len(nombre.strip()) < 3:
        raise NombreEmpresaInvalidoError()
    # No puede ser solo números (ej. "12345")
    if re.match(r"^\d+$", nombre.strip()):
        raise NombreEmpresaInvalidoError()


async def verificar_email_no_existe(db: AsyncSession, email: str) -> None:
    """Verifica que el email no esté registrado en ninguna empresa.

    Raises:
        EmailYaRegistradoError: Si el email ya existe.
    """
    # Buscar en todas las empresas (el email es único globalmente para auth)
    existing = await usuario_repo.get_by_email_global(db, email)
    if existing is not None:
        raise EmailYaRegistradoError()


async def generar_slug_unico(db: AsyncSession, nombre: str) -> str:
    """Genera un slug único para la empresa.

    Si el slug base ya existe, agrega un sufijo numérico.
    """
    base_slug = generar_slug(nombre)
    slug = base_slug
    counter = 1

    while True:
        existing = await empresa_repo.get_by_slug(db, slug)
        if existing is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            # Safety: si llegamos a 100 intentos, algo está muy mal
            raise SlugNoDisponibleError()


async def crear_empresa_y_admin(
    db: AsyncSession,
    *,
    nombre_empresa: str,
    email_admin: str,
    nombre_admin: str,
    apellido_admin: str,
    password: str,
) -> tuple[Empresa, Usuario, Cliente]:
    """Crea una empresa nueva con su admin y cliente "Consumidor Final".

    Esta función es atómica: si cualquier paso falla, hace rollback.

    Args:
        db: Sesión de base de datos.
        nombre_empresa: Nombre de la empresa a crear.
        email_admin: Email del usuario administrador.
        nombre_admin: Nombre del admin.
        apellido_admin: Apellido del admin.
        password: Contraseña en texto plano (se hashea internamente).

    Returns:
        Tupla de (empresa, admin_usuario, cliente_default).

    Raises:
        OnboardingError: Si falla la validación o creación.
    """
    # Fase 1: Validaciones
    validar_nombre_empresa(nombre_empresa)

    # Verificar email no existe
    await verificar_email_no_existe(db, email_admin)

    # Generar slug único
    slug = await generar_slug_unico(db, nombre_empresa)

    # Fase 2: Crear empresa
    empresa = Empresa(
        nombre=nombre_empresa.strip(),
        slug=slug,
        rubro=None,
        moneda="UYU",
        zona_horaria="America/Montevideo",
    )
    db.add(empresa)
    await db.flush()  # Obtener el ID de la empresa

    # Fase 3: Crear usuario admin
    admin = Usuario(
        email=email_admin.strip().lower(),
        nombre=nombre_admin.strip(),
        apellido=apellido_admin.strip(),
        password_hash=get_password_hash(password),
        empresa_id=empresa.id,
        is_admin=True,
        is_active=True,
        rol="admin",
    )
    db.add(admin)

    # Fase 4: Crear cliente "Consumidor Final" (sistema default)
    cliente_default = Cliente(
        empresa_id=empresa.id,
        nombre="Consumidor",
        apellido="Final",
        celular="000000000",
        direccion="Sin dirección",
        es_sistema_default=True,
    )
    db.add(cliente_default)

    # Fase 5: Commit atómico
    logger.info("Intentando commit de onboarding...")
    try:
        await db.commit()
        logger.info("Commit exitoso - empresa_id=%s", empresa.id)
    except Exception as e:
        logger.exception("Error en commit de onboarding: %s", str(e))
        await db.rollback()
        raise

    await db.refresh(empresa)
    await db.refresh(admin)
    await db.refresh(cliente_default)

    logger.info("Onboarding completado: empresa=%s admin=%s", empresa.slug, admin.email)
    return empresa, admin, cliente_default
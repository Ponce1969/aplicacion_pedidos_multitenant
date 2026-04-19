from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    logout_user,
    verify_password,
)
from app.config import settings
from app.models import Usuario
from app.repositories import usuario_repo


async def register_user(  # noqa: PLR0913 — registration needs multiple fields
    db: AsyncSession, email: str, nombre: str, apellido: str, password: str,
    empresa_id: int,
) -> Usuario | str:
    """Registra un usuario nuevo. Devuelve el usuario o un string de error."""
    existing = await usuario_repo.get_by_email(db, email, empresa_id)
    if existing is not None:
        return "El email ya está registrado"

    nuevo = Usuario(
        email=email,
        nombre=nombre,
        apellido=apellido,
        password_hash=get_password_hash(password),
        empresa_id=empresa_id,
    )
    return await usuario_repo.create(db, nuevo)


async def authenticate_user(
    db: AsyncSession, email: str, password: str,
) -> Usuario | None:
    """Autentica un usuario. Devuelve el usuario o None si falla."""
    # Buscar por email sin empresa_id (login no sabe la empresa aún)
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    user.ultimo_login = datetime.now(UTC)
    await db.commit()
    return user


def build_auth_cookies(response: object, user_id: int) -> None:
    """Agrega cookies de access_token y refresh_token a la response."""
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


async def logout_user_service(db: AsyncSession, token: str | None) -> None:
    """Cierra la sesión del usuario."""
    if token is not None:
        await logout_user(token, db)

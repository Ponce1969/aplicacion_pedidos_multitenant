from datetime import UTC, datetime, timedelta
from typing import TypedDict

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import TokenBlacklist, Usuario


class TokenPayload(TypedDict):
    """Estructura del payload JWT decodificado."""

    sub: str
    exp: int
    type: str
    empresa_id: int


# Configurar Argon2 como hash principal
pwd_context = CryptContext(
    schemes=["argon2"],
    default="argon2",
    argon2__time_cost=settings.ARGON2_TIME_COST,
    argon2__memory_cost=settings.ARGON2_MEMORY_COST,
    argon2__parallelism=settings.ARGON2_PARALLELISM,
    argon2__hash_len=settings.ARGON2_HASH_LEN,
    argon2__salt_len=settings.ARGON2_SALT_LEN,
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica contraseña usando Argon2."""
    return bool(pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    """Genera hash Argon2 de la contraseña."""
    hashed: str = pwd_context.hash(password)
    return hashed


def create_access_token(
    data: dict[str, str],
    expires_delta: timedelta | None = None,
) -> str:
    """Crea JWT access token con expiración configurable.

    Args:
        data: Payload del token. Debe contener 'sub' (user_id como string)
              y opcionalmente 'empresa_id'.
        expires_delta: Tiempo hasta expiración. Default: settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Token JWT codificado como string.
    """
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode["exp"] = int(expire.timestamp())
    to_encode["type"] = "access"
    encoded_jwt: str = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict[str, str]) -> str:
    """Crea refresh token con expiración larga.

    Args:
        data: Payload del token. Debe contener 'sub' (user_id como string)
              y opcionalmente 'empresa_id'.

    Returns:
        Token JWT codificado como string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = int(expire.timestamp())
    to_encode["type"] = "refresh"
    encoded_jwt: str = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> Usuario:
    """Obtiene usuario actual desde JWT en cookie o header.

    Busca el token primero en cookie 'access_token' (para HTMX),
    luego en header Authorization Bearer (para API).

    Args:
        request: Request de FastAPI (inyectado automáticamente).
        db: Sesión de base de datos (inyectada por Depends).

    Returns:
        Usuario activo correspondiente al token.

    Raises:
        HTTPException 401: Token ausente, inválido, expirado o revocado.
    """
    # Buscar token en cookie primero (HTMX), luego en header
    token: str | None = request.cookies.get("access_token")
    if not token:
        credentials_header = request.headers.get("Authorization")
        if credentials_header and credentials_header.startswith("Bearer "):
            token = credentials_header[7:]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar si token está en blacklist
    blacklist_query = select(TokenBlacklist).where(TokenBlacklist.token == token)
    blacklist_result = await db.execute(blacklist_query)
    if blacklist_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revocado",
        )

    # Decodificar JWT
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        token_empresa_id: int | None = payload.get("empresa_id")

        if user_id_str is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Obtener usuario de BD — sub es string, convertir a int
    user_query = select(Usuario).where(
        Usuario.id == int(user_id_str),
        Usuario.is_active == True,  # noqa: E712
    )
    user_result = await db.execute(user_query)
    user: Usuario | None = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validar empresa_id del token contra la DB (solo si el token tiene empresa_id)
    if token_empresa_id is not None:
        try:
            token_empresa_id_int = int(token_empresa_id)
        except (ValueError, TypeError):
            token_empresa_id_int = None

        if token_empresa_id_int is not None and token_empresa_id_int != user.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token no pertenece a esta empresa",
            )

    return user


async def get_current_admin_user(
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> Usuario:
    """Verifica que el usuario autenticado sea administrador.

    Acepta tanto el campo legacy is_admin como el nuevo campo rol='admin'.

    Args:
        current_user: Usuario obtenido por get_current_user.

    Returns:
        El mismo usuario si es admin.

    Raises:
        HTTPException 403: El usuario no es administrador.
    """
    if not current_user.is_admin and current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user


async def logout_user(token: str, db: AsyncSession) -> None:
    """Agrega token a blacklist para logout seguro.

    Args:
        token: JWT access token a revocar.
        db: Sesión de base de datos.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_timestamp: int = payload.get("exp", 0)
        expiracion = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        blacklisted_token = TokenBlacklist(
            token=token,
            expiracion=expiracion,
        )
        db.add(blacklisted_token)
        await db.commit()
    except JWTError:
        pass  # Token inválido, no hay nada que blacklisting


async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession,
) -> str:
    """Genera nuevo access token usando refresh token.

    Args:
        refresh_token: JWT refresh token de la cookie.
        db: Sesión de base de datos.

    Returns:
        Nuevo access token JWT.

    Raises:
        HTTPException 401: Refresh token inválido, expirado o revocado.
    """
    # Verificar blacklist
    blacklist_query = select(TokenBlacklist).where(TokenBlacklist.token == refresh_token)
    blacklist_result = await db.execute(blacklist_query)
    if blacklist_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revocado",
        )

    # Decodificar
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id_str is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido",
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        ) from exc

    # Verificar usuario existe y está activo
    user_query = select(Usuario).where(
        Usuario.id == int(user_id_str),
        Usuario.is_active == True,  # noqa: E712
    )
    user_result = await db.execute(user_query)
    user: Usuario | None = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        )

    # Crear nuevo access token
    return create_access_token(data={"sub": str(user.id), "empresa_id": user.empresa_id})

"""Servicio de recuperación de contraseña."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PasswordResetToken, Usuario
from app.services import auth_service
from app.services.email_service import send_password_reset_email


async def create_reset_token(db: AsyncSession, email: str) -> str | None:
    """Crea un token de reseteo y envía email. Retorna mensaje o None si no existe el usuario."""
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        return None  # No revelar si el email existe

    token = secrets.token_urlsafe(32)
    expiracion = datetime.now(UTC) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)

    reset_token = PasswordResetToken(
        usuario_id=usuario.id,
        token=token,
        expiracion=expiracion,
    )
    db.add(reset_token)
    await db.commit()

    send_password_reset_email(email, token, f"{usuario.nombre} {usuario.apellido}")
    return email


async def reset_password(db: AsyncSession, token: str, new_password: str) -> str | None:
    """Resetea la contraseña usando el token. Retorna error o None si OK."""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None:
        return "Token inválido"
    if reset_token.usado:
        return "Token ya fue utilizado"
    if reset_token.expiracion < datetime.now(UTC):
        return "Token expirado"

    # Obtener usuario
    result = await db.execute(select(Usuario).where(Usuario.id == reset_token.usuario_id))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        return "Usuario no encontrado"

    # Hashear nueva contraseña
    usuario.password_hash = auth_service.hash_password(new_password)
    reset_token.usado = True
    await db.commit()

    return None  # OK

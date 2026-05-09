from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Usuario


async def get_by_email(db: AsyncSession, email: str, empresa_id: int) -> Usuario | None:
    result = await db.execute(
        select(Usuario).where(Usuario.email == email, Usuario.empresa_id == empresa_id),
    )
    return result.scalar_one_or_none()


async def get_by_email_global(db: AsyncSession, email: str) -> Usuario | None:
    """Busca un usuario por email sin filtrar por empresa (para onboarding)."""
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int, empresa_id: int) -> Usuario | None:
    result = await db.execute(
        select(Usuario).where(Usuario.id == user_id, Usuario.empresa_id == empresa_id)
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, usuario: Usuario) -> Usuario:
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def list_all(db: AsyncSession, empresa_id: int) -> list[Usuario]:
    result = await db.execute(
        select(Usuario)
        .where(Usuario.empresa_id == empresa_id)
        .order_by(Usuario.fecha_creacion.desc()),
    )
    return list(result.scalars().all())


async def update(db: AsyncSession, usuario: Usuario) -> Usuario:
    """Actualiza un usuario existente. El objeto ya debe tener los campos modificados."""
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def deactivate(db: AsyncSession, user_id: int, empresa_id: int) -> Usuario | None:
    """Desactiva un usuario (soft delete). Retorna None si no existe."""
    usuario = await get_by_id(db, user_id, empresa_id)
    if usuario is None:
        return None
    usuario.is_active = False
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def activate(db: AsyncSession, user_id: int, empresa_id: int) -> Usuario | None:
    """Reactiva un usuario desactivado."""
    usuario = await get_by_id(db, user_id, empresa_id)
    if usuario is None:
        return None
    usuario.is_active = True
    await db.commit()
    await db.refresh(usuario)
    return usuario

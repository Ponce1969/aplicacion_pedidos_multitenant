from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Usuario


async def get_by_email(db: AsyncSession, email: str) -> Usuario | None:
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> Usuario | None:
    result = await db.execute(select(Usuario).where(Usuario.id == user_id))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, usuario: Usuario) -> Usuario:
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def list_all(db: AsyncSession) -> list[Usuario]:
    result = await db.execute(select(Usuario).order_by(Usuario.fecha_creacion.desc()))
    return list(result.scalars().all())

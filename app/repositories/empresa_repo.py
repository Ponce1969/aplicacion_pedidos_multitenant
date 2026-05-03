from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Empresa


async def get_by_id(db: AsyncSession, empresa_id: int) -> Empresa | None:
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> Empresa | None:
    result = await db.execute(select(Empresa).where(Empresa.slug == slug))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, empresa: Empresa) -> Empresa:
    db.add(empresa)
    await db.commit()
    await db.refresh(empresa)
    return empresa
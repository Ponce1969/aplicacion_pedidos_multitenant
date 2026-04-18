from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Engine asíncrono — usa asyncpg como driver
engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

# Fábrica de sesiones asíncronas
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection: provee una sesión de BD por request.

    Yields:
        AsyncSession: sesión activa de la base de datos.

    Usage en FastAPI:
        db: AsyncSession = Depends(get_db)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Crea todas las tablas definidas en los modelos.

    Se ejecuta en el lifespan de FastAPI al arrancar.
    En producción usar Alembic migrations en vez de create_all.
    """
    async with engine.begin() as conn:
        from app.models import Base as ModelBase

        await conn.run_sync(ModelBase.metadata.create_all)

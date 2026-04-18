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
    Es idempotente: no recrea tablas que ya existen.
    Las migraciones con Alembic se ejecutan desde el entrypoint Docker.
    También crea la empresa default y asigna usuarios existentes sin empresa.
    """
    async with engine.begin() as conn:
        from app.models import Base as ModelBase

        await conn.run_sync(ModelBase.metadata.create_all)

    # Crear empresa default si no existe
    from sqlalchemy import select, update

    from app.models import Empresa, Usuario

    async with async_session_factory() as session:
        result = await session.execute(select(Empresa).where(Empresa.slug == "default"))
        empresa = result.scalar_one_or_none()

        if empresa is None:
            empresa = Empresa(
                nombre="Mi Empresa",
                slug="default",
                rubro="General",
            )
            session.add(empresa)
            await session.commit()
            await session.refresh(empresa)

        # Asignar empresa_id a usuarios que no tengan uno (migración)
        await session.execute(
            update(Usuario)
            .where(Usuario.empresa_id.is_(None))
            .values(empresa_id=empresa.id),
        )
        await session.commit()

        # Asignar empresa_id a pedidos que no tengan uno (migración)
        from app.models import Pedido

        await session.execute(
            update(Pedido)
            .where(Pedido.empresa_id.is_(None))
            .values(empresa_id=empresa.id),
        )
        await session.commit()

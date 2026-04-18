import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_access_token, get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models import Usuario

# SQLite en memoria para tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Crea un engine SQLite en memoria para cada test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Crea una sesión de BD para cada test."""
    async_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(test_session: AsyncSession) -> Usuario:
    """Crea un usuario de prueba."""
    user = Usuario(
        email="test@example.com",
        nombre="Test",
        apellido="User",
        password_hash=get_password_hash("Test123!"),
        is_active=True,
        is_admin=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_admin_user(test_session: AsyncSession) -> Usuario:
    """Crea un usuario admin de prueba."""
    admin = Usuario(
        email="admin@example.com",
        nombre="Admin",
        apellido="User",
        password_hash=get_password_hash("Admin123!"),
        is_active=True,
        is_admin=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)
    return admin


@pytest.fixture
async def test_token(test_user: Usuario) -> str:
    """Crea un token JWT para el usuario de prueba."""
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
async def client(test_session: AsyncSession):
    """Crea un cliente HTTP asíncrono para tests."""

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

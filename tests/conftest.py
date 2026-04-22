"""Fixtures compartidas para todos los tests."""

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from jose import jwt

# Forzar modo development para tests (CSRF off, cookies insecure)
os.environ["APP_ENV"] = "development"
os.environ["DEBUG"] = "true"
# Forzar SQLite en memoria para evitar importar psycopg2
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.auth import create_access_token, get_password_hash
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    Empresa,
    Pedido,
    Usuario,
    PedidoItem,
    Producto,
    Cliente,
    PasswordResetToken,
    TokenBlacklist,
)
from app.rate_limiter import login_limiter, register_limiter, forgot_password_limiter


# Base de datos en memoria para tests (limpio entre sesiones)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limiters():
    """Limpia los rate limiters antes de cada test."""
    login_limiter._requests.clear()
    register_limiter._requests.clear()
    forgot_password_limiter._requests.clear()
    yield


@pytest_asyncio.fixture
async def db_session(engine):
    """Sesión de BD limpia para cada test."""
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Cliente HTTP asíncrono para tests."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def empresa_a(db_session):
    """Empresa A (tenant 1)."""
    empresa = Empresa(nombre="Empresa A", slug="empresa-a", rubro="Construcción")
    db_session.add(empresa)
    await db_session.commit()
    await db_session.refresh(empresa)
    return empresa


@pytest_asyncio.fixture
async def empresa_b(db_session):
    """Empresa B (tenant 2)."""
    empresa = Empresa(nombre="Empresa B", slug="empresa-b", rubro="Maderera")
    db_session.add(empresa)
    await db_session.commit()
    await db_session.refresh(empresa)
    return empresa


@pytest_asyncio.fixture
async def user_empresa_a(db_session, empresa_a):
    """Usuario admin de Empresa A."""
    user = Usuario(
        email="admin@empresa-a.com",
        nombre="Admin",
        apellido="EmpresaA",
        password_hash=get_password_hash("Test123!"),
        is_admin=True,
        is_active=True,
        empresa_id=empresa_a.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_empresa_b(db_session, empresa_b):
    """Usuario admin de Empresa B."""
    user = Usuario(
        email="admin@empresa-b.com",
        nombre="Admin",
        apellido="EmpresaB",
        password_hash=get_password_hash("Test123!"),
        is_admin=True,
        is_active=True,
        empresa_id=empresa_b.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def pedido_empresa_a(db_session, empresa_a, user_empresa_a):
    """Pedido perteneciente a Empresa A."""
    pedido = Pedido(
        nombre="Cliente",
        apellido="A",
        celular="099111111",
        direccion="Calle A 123",
        hora_entrega="10:00",
        pedido_detalle="10 bolsas de cemento",
        total=50000,
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="pendiente",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def pedido_empresa_b(db_session, empresa_b, user_empresa_b):
    """Pedido perteneciente a Empresa B."""
    pedido = Pedido(
        nombre="Cliente",
        apellido="B",
        celular="099222222",
        direccion="Calle B 456",
        hora_entrega="14:00",
        pedido_detalle="5 metros de madera",
        total=30000,
        empresa_id=empresa_b.id,
        usuario_id=user_empresa_b.id,
        estado="pendiente",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def pedido_empresa_a_2(db_session, empresa_a, user_empresa_a):
    """Segundo pedido para Empresa A (util para listados y busquedas)."""
    pedido = Pedido(
        nombre="SegundoCliente",
        apellido="A2",
        celular="099333333",
        direccion="Calle A 789",
        hora_entrega="16:00",
        pedido_detalle="Cemento 50kg - 5 unidades",
        total=75000,
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="pendiente",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def expired_access_token(user_empresa_a):
    """Token JWT de acceso ya expirado."""
    return create_access_token(
        data={"sub": str(user_empresa_a.id), "empresa_id": user_empresa_a.empresa_id},
        expires_delta=timedelta(seconds=-1),
    )


@pytest_asyncio.fixture
async def expired_refresh_token(user_empresa_a):
    """Token JWT de refresh ya expirado."""
    payload = {
        "sub": str(user_empresa_a.id),
        "empresa_id": user_empresa_a.empresa_id,
        "exp": int((datetime.now(UTC) - timedelta(days=1)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest_asyncio.fixture
async def valid_password_reset_token(db_session, user_empresa_a):
    """PasswordResetToken valido y no usado."""
    token = PasswordResetToken(
        usuario_id=user_empresa_a.id,
        token="valid_reset_token_123",
        expiracion=datetime.now(UTC) + timedelta(minutes=30),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def used_password_reset_token(db_session, user_empresa_a):
    """PasswordResetToken ya utilizado."""
    token = PasswordResetToken(
        usuario_id=user_empresa_a.id,
        token="used_reset_token_456",
        expiracion=datetime.now(UTC) + timedelta(minutes=30),
        usado=True,
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def expired_password_reset_token(db_session, user_empresa_a):
    """PasswordResetToken expirado."""
    token = PasswordResetToken(
        usuario_id=user_empresa_a.id,
        token="expired_reset_token_789",
        expiracion=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def producto_empresa_a(db_session, empresa_a):
    """Producto activo para Empresa A."""
    producto = Producto(
        nombre="Cemento 25kg",
        sku="CEM-25",
        precio_base=Decimal("450.00"),
        empresa_id=empresa_a.id,
        is_active=True,
    )
    db_session.add(producto)
    await db_session.commit()
    await db_session.refresh(producto)
    return producto


@pytest_asyncio.fixture
async def producto_empresa_b(db_session, empresa_b):
    """Producto activo para Empresa B."""
    producto = Producto(
        nombre="Madera pino 2x4",
        sku="MAD-2X4",
        precio_base=Decimal("350.00"),
        empresa_id=empresa_b.id,
        is_active=True,
    )
    db_session.add(producto)
    await db_session.commit()
    await db_session.refresh(producto)
    return producto


@pytest_asyncio.fixture
async def cliente_empresa_a(db_session, empresa_a):
    """Cliente de Empresa A."""
    cliente = Cliente(
        nombre="Juan",
        apellido="Perez",
        celular="099123456",
        direccion="Av. Italia 1234",
        empresa_id=empresa_a.id,
    )
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)
    return cliente


@pytest_asyncio.fixture
async def cliente_empresa_b(db_session, empresa_b):
    """Cliente de Empresa B."""
    cliente = Cliente(
        nombre="Maria",
        apellido="Garcia",
        celular="099654321",
        direccion="Calle B 999",
        empresa_id=empresa_b.id,
    )
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)
    return cliente

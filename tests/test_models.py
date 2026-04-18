from datetime import UTC, datetime

from app.models import Pedido, TokenBlacklist, Usuario


async def test_usuario_creation(test_session):
    """Test creación de usuario."""
    user = Usuario(
        email="test@example.com",
        nombre="Test",
        apellido="User",
        password_hash="hashed_password",
        is_active=True,
        is_admin=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_admin is False


async def test_pedido_creation(test_session, test_user):
    """Test creación de pedido."""
    pedido = Pedido(
        usuario_id=test_user.id,
        nombre="Juan",
        apellido="Pérez",
        celular="+595991234567",
        direccion="Calle 123",
        hora_entrega="14:00",
        fecha_entrega=datetime.now(UTC),
        pedido_detalle="Clavos - 2kg",
        total=50000.0,
        estado="pendiente",
    )
    test_session.add(pedido)
    await test_session.commit()
    await test_session.refresh(pedido)

    assert pedido.id is not None
    assert pedido.usuario_id == test_user.id
    assert pedido.estado == "pendiente"
    assert pedido.total == 50000.0


async def test_token_blacklist_creation(test_session):
    """Test creación de token blacklist."""
    token = TokenBlacklist(
        token="expired_token_123",
        expiracion=datetime.now(UTC),
    )
    test_session.add(token)
    await test_session.commit()
    await test_session.refresh(token)

    assert token.id is not None
    assert token.token == "expired_token_123"

"""Tests unitarios para repositories.

Fase 4: Tests de repositories (cliente_repo, producto_repo, usuario_repo, pedido_repo)
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models import Cliente, Pedido, PedidoItem, Producto, Usuario
from app.repositories import cliente_repo, pedido_repo, producto_repo, usuario_repo


# ==================== FIXTURES ADICIONALES ====================


@pytest_asyncio.fixture
async def pedido_con_senia(db_session, empresa_a, user_empresa_a):
    """Pedido con seña/adelanto."""
    pedido = Pedido(
        nombre="ClienteSeña",
        apellido="Test",
        celular="099999999",
        direccion="Calle Seña 123",
        hora_entrega="09:00",
        pedido_detalle="Producto con seña",
        total=Decimal("100000"),
        senia=Decimal("30000"),
        estado_pago="parcial",
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="pendiente",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def pedido_pagado(db_session, empresa_a, user_empresa_a):
    """Pedido completamente pagado (seña = total)."""
    pedido = Pedido(
        nombre="ClientePagado",
        apellido="Test",
        celular="099888888",
        direccion="Calle Pagado 456",
        hora_entrega="10:00",
        pedido_detalle="Producto pagado",
        total=Decimal("50000"),
        senia=Decimal("50000"),
        estado_pago="pagado",
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="pendiente",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def pedido_con_fecha_entrega(db_session, empresa_a, user_empresa_a):
    """Pedido con fecha de entrega específica."""
    pedido = Pedido(
        nombre="ClienteEntrega",
        apellido="Test",
        celular="099777777",
        direccion="Calle Entrega 789",
        hora_entrega="11:00",
        pedido_detalle="Entrega programada",
        total=Decimal("25000"),
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="pendiente",
        fecha_entrega=datetime(2026, 4, 25, 10, 0, 0, tzinfo=UTC),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


@pytest_asyncio.fixture
async def pedido_cancelado(db_session, empresa_a, user_empresa_a):
    """Pedido cancelado."""
    pedido = Pedido(
        nombre="ClienteCancelado",
        apellido="Test",
        celular="099666666",
        direccion="Calle Cancel 000",
        hora_entrega="12:00",
        pedido_detalle="Pedido cancelado",
        total=Decimal("15000"),
        empresa_id=empresa_a.id,
        usuario_id=user_empresa_a.id,
        estado="cancelado",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


# ==================== PEDIDO REPO ====================


@pytest.mark.asyncio
class TestPedidoRepo:
    """Tests para pedido_repo."""

    async def test_get_by_id_existente(self, db_session, pedido_empresa_a):
        """get_by_id debe retornar el pedido si existe."""
        result = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id)

        assert result is not None
        assert result.id == pedido_empresa_a.id
        assert result.nombre == "Cliente"

    async def test_get_by_id_no_existente(self, db_session):
        """get_by_id debe retornar None si no existe."""
        result = await pedido_repo.get_by_id(db_session, 99999)

        assert result is None

    async def test_create(self, db_session, empresa_a, user_empresa_a):
        """create debe persistir un nuevo pedido."""
        pedido = Pedido(
            nombre="Nuevo",
            apellido="Cliente",
            celular="099000000",
            direccion="Nueva Dirección",
            hora_entrega="08:00",
            pedido_detalle="Nuevo pedido test",
            total=Decimal("10000"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
        )

        result = await pedido_repo.create(db_session, pedido)

        assert result.id is not None
        assert result.nombre == "Nuevo"

    async def test_create_con_senia(self, db_session, empresa_a, user_empresa_a):
        """create debe persistir pedido con seña."""
        pedido = Pedido(
            nombre="ConSeña",
            apellido="Test",
            celular="099111222",
            direccion="Dir",
            hora_entrega="08:00",
            pedido_detalle="Test seña",
            total=Decimal("50000"),
            senia=Decimal("15000"),
            estado_pago="parcial",
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
        )

        result = await pedido_repo.create(db_session, pedido)

        assert result.senia == Decimal("15000")
        assert result.estado_pago == "parcial"

    async def test_search_by_celular(self, db_session, pedido_empresa_a):
        """search debe encontrar por celular."""
        result = await pedido_repo.search_by_celular_or_apellido(
            db_session, "099111111", pedido_empresa_a.empresa_id,
        )

        assert len(result) == 1
        assert result[0].celular == "099111111"

    async def test_search_by_apellido(self, db_session, pedido_empresa_a):
        """search debe encontrar por apellido (case-insensitive)."""
        result = await pedido_repo.search_by_celular_or_apellido(
            db_session, "A", pedido_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert any(p.apellido == "A" for p in result)

    async def test_search_by_nombre(self, db_session, pedido_empresa_a):
        """search debe encontrar por nombre."""
        result = await pedido_repo.search_by_celular_or_apellido(
            db_session, "Cliente", pedido_empresa_a.empresa_id,
        )

        assert len(result) >= 1

    async def test_search_no_results(self, db_session, empresa_a):
        """search debe retornar lista vacía si no hay coincidencias."""
        result = await pedido_repo.search_by_celular_or_apellido(
            db_session, "ZZZZZZZZ", empresa_a.id,
        )

        assert result == []

    async def test_search_otra_empresa_no_acceso(
        self, db_session, pedido_empresa_a, empresa_b,
    ):
        """search NO debe retornar pedidos de otra empresa."""
        result = await pedido_repo.search_by_celular_or_apellido(
            db_session, "099111111", empresa_b.id,
        )

        assert len(result) == 0

    async def test_get_by_month(self, db_session, empresa_a, user_empresa_a):
        """get_by_month debe retornar pedidos del mes actual."""
        # Crear pedido con fecha_creacion reciente
        pedido = Pedido(
            nombre="Reciente",
            apellido="Test",
            celular="099555555",
            direccion="Dir",
            hora_entrega="08:00",
            pedido_detalle="Pedido reciente",
            total=Decimal("1000"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
        )
        await pedido_repo.create(db_session, pedido)

        primer_dia = date.today().replace(day=1)
        result = await pedido_repo.get_by_month(db_session, primer_dia, empresa_a.id)

        assert len(result) >= 1
        assert any(p.nombre == "Reciente" for p in result)

    async def test_get_pending_by_empresa(self, db_session, pedido_empresa_a):
        """get_pending_by_empresa debe retornar solo pendientes."""
        result = await pedido_repo.get_pending_by_empresa(
            db_session, pedido_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert all(p.estado == "pendiente" for p in result)

    async def test_get_pending_filtrado_por_fecha(
        self, db_session, pedido_con_fecha_entrega, empresa_a,
    ):
        """get_pending_by_empresa debe filtrar por fecha de entrega."""
        result = await pedido_repo.get_pending_by_empresa(
            db_session, empresa_a.id, fecha=date(2026, 4, 25),
        )

        assert len(result) == 1
        assert result[0].id == pedido_con_fecha_entrega.id

    async def test_get_pending_excluye_cancelados(
        self, db_session, pedido_cancelado, empresa_a,
    ):
        """get_pending_by_empresa NO debe incluir cancelados."""
        result = await pedido_repo.get_pending_by_empresa(
            db_session, empresa_a.id,
        )

        assert not any(p.estado == "cancelado" for p in result)

    async def test_delete_pedido_existente(self, db_session, pedido_empresa_a):
        """delete_pedido debe eliminar y retornar True."""
        result = await pedido_repo.delete_pedido(
            db_session, pedido_empresa_a.id,
        )

        assert result is True
        # Verificar que no existe más
        deleted = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id)
        assert deleted is None

    async def test_delete_pedido_no_existente(self, db_session):
        """delete_pedido debe retornar False si no existe."""
        result = await pedido_repo.delete_pedido(db_session, 99999)

        assert result is False


# ==================== PRODUCTO REPO ====================


@pytest.mark.asyncio
class TestProductoRepo:
    """Tests para producto_repo."""

    async def test_get_by_id_existente(self, db_session, producto_empresa_a):
        """get_by_id debe retornar el producto."""
        result = await producto_repo.get_by_id(db_session, producto_empresa_a.id)

        assert result is not None
        assert result.nombre == "Cemento 25kg"
        assert result.sku == "CEM-25"

    async def test_get_by_id_no_existente(self, db_session):
        """get_by_id debe retornar None."""
        result = await producto_repo.get_by_id(db_session, 99999)

        assert result is None

    async def test_search_por_nombre(self, db_session, producto_empresa_a):
        """search debe encontrar por nombre."""
        result = await producto_repo.search(
            db_session, "cemento", producto_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert any(p.nombre == "Cemento 25kg" for p in result)

    async def test_search_por_sku(self, db_session, producto_empresa_a):
        """search debe encontrar por SKU."""
        result = await producto_repo.search(
            db_session, "CEM", producto_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert any(p.sku == "CEM-25" for p in result)

    async def test_search_limit_20(self, db_session, empresa_a):
        """search debe limitar a 20 resultados."""
        # Crear 25 productos
        for i in range(25):
            p = Producto(
                nombre=f"Producto {i}",
                sku=f"SKU-{i}",
                precio_base=Decimal("100"),
                empresa_id=empresa_a.id,
                is_active=True,
            )
            db_session.add(p)
        await db_session.commit()

        result = await producto_repo.search(db_session, "Producto", empresa_a.id)

        assert len(result) == 20

    async def test_search_excluye_inactivos(self, db_session, empresa_a):
        """search NO debe incluir productos inactivos."""
        p = Producto(
            nombre="ProductoInactivo",
            sku="INACT-01",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=False,
        )
        db_session.add(p)
        await db_session.commit()

        result = await producto_repo.search(
            db_session, "ProductoInactivo", empresa_a.id,
        )

        assert len(result) == 0

    async def test_list_active(self, db_session, producto_empresa_a, empresa_a):
        """list_active debe retornar solo productos activos."""
        # Agregar inactivo
        p = Producto(
            nombre="Inactivo",
            sku="INACT",
            precio_base=Decimal("50"),
            empresa_id=empresa_a.id,
            is_active=False,
        )
        db_session.add(p)
        await db_session.commit()

        result = await producto_repo.list_active(db_session, empresa_a.id)

        assert len(result) >= 1
        assert all(p.is_active for p in result)
        assert not any(p.nombre == "Inactivo" for p in result)

    async def test_create(self, db_session, empresa_a):
        """create debe persistir producto."""
        producto = Producto(
            nombre="Arena",
            sku="ARE-50",
            precio_base=Decimal("200"),
            empresa_id=empresa_a.id,
        )

        result = await producto_repo.create(db_session, producto)

        assert result.id is not None
        assert result.nombre == "Arena"


# ==================== CLIENTE REPO ====================


@pytest.mark.asyncio
class TestClienteRepo:
    """Tests para cliente_repo."""

    async def test_get_by_id_existente(self, db_session, cliente_empresa_a):
        """get_by_id debe retornar el cliente."""
        result = await cliente_repo.get_by_id(db_session, cliente_empresa_a.id)

        assert result is not None
        assert result.nombre == "Juan"
        assert result.apellido == "Perez"

    async def test_get_by_id_no_existente(self, db_session):
        """get_by_id debe retornar None."""
        result = await cliente_repo.get_by_id(db_session, 99999)

        assert result is None

    async def test_get_by_celular_existente(self, db_session, cliente_empresa_a):
        """get_by_celular debe encontrar por celular exacto."""
        result = await cliente_repo.get_by_celular(
            db_session, "099123456", cliente_empresa_a.empresa_id,
        )

        assert result is not None
        assert result.celular == "099123456"

    async def test_get_by_celular_no_existente(self, db_session, empresa_a):
        """get_by_celular debe retornar None si no existe."""
        result = await cliente_repo.get_by_celular(
            db_session, "099000000", empresa_a.id,
        )

        assert result is None

    async def test_get_by_celular_otra_empresa(
        self, db_session, cliente_empresa_a, empresa_b,
    ):
        """get_by_celular NO debe retornar cliente de otra empresa."""
        result = await cliente_repo.get_by_celular(
            db_session, "099123456", empresa_b.id,
        )

        assert result is None

    async def test_search_por_nombre(self, db_session, cliente_empresa_a):
        """search debe encontrar por nombre."""
        result = await cliente_repo.search(
            db_session, "Juan", cliente_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert any(c.nombre == "Juan" for c in result)

    async def test_search_por_apellido(self, db_session, cliente_empresa_a):
        """search debe encontrar por apellido."""
        result = await cliente_repo.search(
            db_session, "Perez", cliente_empresa_a.empresa_id,
        )

        assert len(result) >= 1
        assert any(c.apellido == "Perez" for c in result)

    async def test_search_por_celular(self, db_session, cliente_empresa_a):
        """search debe encontrar por celular parcial."""
        result = await cliente_repo.search(
            db_session, "123456", cliente_empresa_a.empresa_id,
        )

        assert len(result) >= 1

    async def test_search_otra_empresa(self, db_session, cliente_empresa_a, empresa_b):
        """search NO debe retornar clientes de otra empresa."""
        result = await cliente_repo.search(
            db_session, "Juan", empresa_b.id,
        )

        assert len(result) == 0

    async def test_create(self, db_session, empresa_a):
        """create debe persistir cliente."""
        cliente = Cliente(
            nombre="Pedro",
            apellido="Lopez",
            celular="099777777",
            direccion="Av. Brasil 100",
            empresa_id=empresa_a.id,
        )

        result = await cliente_repo.create(db_session, cliente)

        assert result.id is not None
        assert result.nombre == "Pedro"

    async def test_create_or_get_existente(self, db_session, cliente_empresa_a):
        """create_or_get_by_celular debe retornar existente."""
        nuevo = Cliente(
            nombre="Otro",
            apellido="Nombre",
            celular="099123456",  # Mismo celular que cliente_empresa_a
            direccion="Otra dirección",
            empresa_id=cliente_empresa_a.empresa_id,
        )

        result = await cliente_repo.create_or_get_by_celular(db_session, nuevo)

        assert result.id == cliente_empresa_a.id
        assert result.nombre == "Juan"  # Debe retornar el original

    async def test_create_or_get_nuevo(self, db_session, empresa_a):
        """create_or_get_by_celular debe crear si no existe."""
        nuevo = Cliente(
            nombre="Nuevo",
            apellido="Cliente",
            celular="099888888",
            direccion="Dir nueva",
            empresa_id=empresa_a.id,
        )

        result = await cliente_repo.create_or_get_by_celular(db_session, nuevo)

        assert result.id is not None
        assert result.nombre == "Nuevo"


# ==================== USUARIO REPO ====================


@pytest.mark.asyncio
class TestUsuarioRepo:
    """Tests para usuario_repo."""

    async def test_get_by_email_existente(self, db_session, user_empresa_a):
        """get_by_email debe retornar el usuario."""
        result = await usuario_repo.get_by_email(
            db_session, "admin@empresa-a.com", user_empresa_a.empresa_id,
        )

        assert result is not None
        assert result.email == "admin@empresa-a.com"

    async def test_get_by_email_no_existente(self, db_session, empresa_a):
        """get_by_email debe retornar None."""
        result = await usuario_repo.get_by_email(
            db_session, "noexiste@test.com", empresa_a.id,
        )

        assert result is None

    async def test_get_by_email_otra_empresa(
        self, db_session, user_empresa_a, empresa_b,
    ):
        """get_by_email NO debe retornar usuario de otra empresa."""
        result = await usuario_repo.get_by_email(
            db_session, "admin@empresa-a.com", empresa_b.id,
        )

        assert result is None

    async def test_get_by_id_existente(self, db_session, user_empresa_a):
        """get_by_id debe retornar el usuario."""
        result = await usuario_repo.get_by_id(db_session, user_empresa_a.id)

        assert result is not None
        assert result.id == user_empresa_a.id

    async def test_get_by_id_no_existente(self, db_session):
        """get_by_id debe retornar None."""
        result = await usuario_repo.get_by_id(db_session, 99999)

        assert result is None

    async def test_create(self, db_session, empresa_a):
        """create debe persistir usuario."""
        from app.auth import get_password_hash

        usuario = Usuario(
            email="nuevo@test.com",
            nombre="Nuevo",
            apellido="Usuario",
            password_hash=get_password_hash("Password123!"),
            empresa_id=empresa_a.id,
        )

        result = await usuario_repo.create(db_session, usuario)

        assert result.id is not None
        assert result.email == "nuevo@test.com"

    async def test_list_all(self, db_session, empresa_a, user_empresa_a):
        """list_all debe retornar usuarios de la empresa."""
        # Crear otro usuario
        from app.auth import get_password_hash

        usuario2 = Usuario(
            email="otro@test.com",
            nombre="Otro",
            apellido="Usuario",
            password_hash=get_password_hash("Password123!"),
            empresa_id=empresa_a.id,
        )
        db_session.add(usuario2)
        await db_session.commit()

        result = await usuario_repo.list_all(db_session, empresa_a.id)

        assert len(result) >= 2
        assert any(u.email == "admin@empresa-a.com" for u in result)
        assert any(u.email == "otro@test.com" for u in result)

    async def test_list_all_otra_empresa(
        self, db_session, user_empresa_a, empresa_b,
    ):
        """list_all NO debe retornar usuarios de otra empresa."""
        result = await usuario_repo.list_all(db_session, empresa_b.id)

        assert len(result) == 0

"""Tests para M-05: Múltiples direcciones de entrega por cliente."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cliente, ClienteDireccion
from app.repositories import cliente_repo


class TestClienteDireccionModel:
    """M-05: Verificar que el modelo ClienteDireccion existe."""

    def test_cliente_direccion_model_existe(self):
        assert hasattr(ClienteDireccion, "__tablename__")
        assert ClienteDireccion.__tablename__ == "cliente_direcciones"

    def test_cliente_tiene_relacion_direcciones(self, cliente_empresa_a):
        """Cliente tiene relationship 'direcciones'."""
        assert hasattr(cliente_empresa_a, "direcciones")


class TestGetDirecciones:
    """M-05: Obtener direcciones de un cliente."""

    async def test_get_direcciones_cliente(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Obtiene todas las direcciones de un cliente."""
        dir1 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Casa",
            direccion="Av. Italia 1234",
            es_principal=True,
        )
        dir2 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Trabajo",
            direccion="Rambla 5678",
            es_principal=False,
        )
        db_session.add_all([dir1, dir2])
        await db_session.commit()

        direcciones = await cliente_repo.get_direcciones(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert len(direcciones) == 2

    async def test_direcciones_ordenadas_principal_primero(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Dirección principal aparece primero."""
        dir1 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Trabajo",
            direccion="Rambla 5678",
            es_principal=False,
        )
        dir2 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Casa",
            direccion="Av. Italia 1234",
            es_principal=True,
        )
        db_session.add_all([dir1, dir2])
        await db_session.commit()

        direcciones = await cliente_repo.get_direcciones(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert direcciones[0].es_principal is True
        assert direcciones[0].descripcion == "Casa"

    async def test_get_direcciones_cliente_vacio(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Cliente sin direcciones retorna lista vacía."""
        direcciones = await cliente_repo.get_direcciones(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert len(direcciones) == 0

    async def test_get_direcciones_multi_tenant(
        self, db_session, empresa_a, empresa_b, cliente_empresa_a, cliente_empresa_b
    ):
        """Direcciones son por empresa (multi-tenant)."""
        dir_a = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Casa A",
            direccion="Dir A",
            es_principal=True,
        )
        dir_b = ClienteDireccion(
            cliente_id=cliente_empresa_b.id,
            empresa_id=empresa_b.id,
            descripcion="Casa B",
            direccion="Dir B",
            es_principal=True,
        )
        db_session.add_all([dir_a, dir_b])
        await db_session.commit()

        direcciones_a = await cliente_repo.get_direcciones(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        direcciones_b = await cliente_repo.get_direcciones(
            db_session, cliente_empresa_b.id, empresa_b.id
        )
        assert len(direcciones_a) == 1
        assert direcciones_a[0].descripcion == "Casa A"
        assert len(direcciones_b) == 1
        assert direcciones_b[0].descripcion == "Casa B"


class TestGetDireccionPrincipal:
    """M-05: Obtener dirección principal."""

    async def test_get_direccion_principal(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Retorna la dirección marcada como principal."""
        dir1 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Trabajo",
            direccion="Rambla 5678",
            es_principal=False,
        )
        dir2 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Casa",
            direccion="Av. Italia 1234",
            es_principal=True,
        )
        db_session.add_all([dir1, dir2])
        await db_session.commit()

        principal = await cliente_repo.get_direccion_principal(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert principal is not None
        assert principal.descripcion == "Casa"
        assert principal.direccion == "Av. Italia 1234"

    async def test_sin_principal_retorna_none(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Si no hay principal, retorna None."""
        dir1 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Trabajo",
            direccion="Rambla 5678",
            es_principal=False,
        )
        db_session.add(dir1)
        await db_session.commit()

        principal = await cliente_repo.get_direccion_principal(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert principal is None


class TestCreateDireccion:
    """M-05: Crear dirección."""

    async def test_create_direccion(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Crea una nueva dirección para un cliente."""
        direccion = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Depósito",
            direccion="Ruta 5 km 25",
            es_principal=False,
        )
        resultado = await cliente_repo.create_direccion(db_session, direccion)
        assert resultado.id is not None
        assert resultado.descripcion == "Depósito"


class TestSetPrincipal:
    """M-05: Marcar dirección como principal."""

    async def test_set_principal(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Al marcar una como principal, las demás se desmarcan."""
        dir1 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Casa",
            direccion="Av. Italia 1234",
            es_principal=True,
        )
        dir2 = ClienteDireccion(
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            descripcion="Trabajo",
            direccion="Rambla 5678",
            es_principal=False,
        )
        db_session.add_all([dir1, dir2])
        await db_session.commit()

        # Marcar dir2 como principal
        await cliente_repo.set_principal(
            db_session, dir2.id, cliente_empresa_a.id, empresa_a.id
        )

        # Refrescar
        await db_session.refresh(dir1)
        await db_session.refresh(dir2)

        assert dir1.es_principal is False
        assert dir2.es_principal is True


class TestPedidoSnapshotDireccion:
    """M-05: Pedido guarda snapshot de dirección (texto, no FK)."""

    async def test_pedido_guarda_texto_direccion(
        self, db_session, empresa_a, user_empresa_a, cliente_empresa_a
    ):
        """Pedido.direccion es un String, no una FK a ClienteDireccion."""
        from app.models import Pedido

        pedido = Pedido(
            nombre="Juan",
            apellido="Perez",
            celular="099123456",
            direccion="Av. Italia 1234, Apt 3B",  # Texto snapshot
            hora_entrega="10:00",
            pedido_detalle="Test",
            total=Decimal("1000"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
            cliente_id=cliente_empresa_a.id,
        )
        db_session.add(pedido)
        await db_session.commit()
        await db_session.refresh(pedido)

        # La dirección es texto plano, no una FK
        assert pedido.direccion == "Av. Italia 1234, Apt 3B"
        assert isinstance(pedido.direccion, str)

    async def test_direccion_pedido_no_cambia_si_cliente_modifica(
        self, db_session, empresa_a, user_empresa_a, cliente_empresa_a
    ):
        """Si el cliente cambia su dirección, el pedido viejo mantiene la original."""
        from app.models import Pedido

        # Crear pedido con dirección original
        pedido = Pedido(
            nombre="Juan",
            apellido="Perez",
            celular="099123456",
            direccion="Av. Italia 1234",
            hora_entrega="10:00",
            pedido_detalle="Test",
            total=Decimal("1000"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
            cliente_id=cliente_empresa_a.id,
        )
        db_session.add(pedido)
        await db_session.commit()

        # Cambiar dirección del cliente
        cliente_empresa_a.direccion = "Nueva Dirección 9999"
        await db_session.commit()

        # El pedido mantiene la dirección original
        await db_session.refresh(pedido)
        assert pedido.direccion == "Av. Italia 1234"

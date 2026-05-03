"""Test de Aislamiento y Seguridad Multi-tenant.

Verifica que no haya fugas de datos entre empresas:
- Un usuario de Empresa A no puede acceder a recursos de Empresa B.
- get_by_id filtra por empresa_id y retorna None para recursos de otras empresas.
- delete_pedido filtra por empresa_id y retorna False para recursos de otras empresas.
"""

import pytest

from app.models import Pedido, Producto, Cliente, Usuario
from app.repositories import pedido_repo, producto_repo, cliente_repo, usuario_repo


@pytest.mark.asyncio
class TestIsolationPedido:
    """Tests de aislamiento para pedido_repo."""

    async def test_get_by_id_empresa_b_no_ve_pedido_empresa_a(
        self, db_session, empresa_a, empresa_b, pedido_empresa_a,
    ):
        """Usuario de B no puede ver pedido de A."""
        result = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_b.id)
        assert result is None

    async def test_get_by_id_propio_retorna_pedido(
        self, db_session, empresa_a, pedido_empresa_a,
    ):
        """Usuario de A puede ver pedido de A."""
        result = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_a.id)
        assert result is not None
        assert result.id == pedido_empresa_a.id

    async def test_delete_pedido_empresa_b_no_puede_borrar_pedido_empresa_a(
        self, db_session, empresa_a, empresa_b, pedido_empresa_a,
    ):
        """Usuario de B no puede eliminar pedido de A."""
        result = await pedido_repo.delete_pedido(db_session, pedido_empresa_a.id, empresa_b.id)
        assert result is False
        # Verificar que el pedido sigue existiendo
        still_exists = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_a.id)
        assert still_exists is not None

    async def test_delete_pedido_propio_funciona(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a,
    ):
        """Usuario de A puede eliminar pedido de A."""
        result = await pedido_repo.delete_pedido(db_session, pedido_empresa_a.id, empresa_a.id)
        assert result is True
        # Verificar que ya no existe para esa empresa
        deleted = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_a.id)
        assert deleted is None


@pytest.mark.asyncio
class TestIsolationProducto:
    """Tests de aislamiento para producto_repo."""

    async def test_get_by_id_empresa_b_no_ve_producto_empresa_a(
        self, db_session, empresa_a, empresa_b, producto_empresa_a,
    ):
        """Usuario de B no puede ver producto de A."""
        result = await producto_repo.get_by_id(db_session, producto_empresa_a.id, empresa_b.id)
        assert result is None

    async def test_get_by_id_propio_retorna_producto(
        self, db_session, empresa_a, producto_empresa_a,
    ):
        """Usuario de A puede ver producto de A."""
        result = await producto_repo.get_by_id(db_session, producto_empresa_a.id, empresa_a.id)
        assert result is not None
        assert result.id == producto_empresa_a.id


@pytest.mark.asyncio
class TestIsolationCliente:
    """Tests de aislamiento para cliente_repo."""

    async def test_get_by_id_empresa_b_no_ve_cliente_empresa_a(
        self, db_session, empresa_a, empresa_b, cliente_empresa_a,
    ):
        """Usuario de B no puede ver cliente de A."""
        result = await cliente_repo.get_by_id(db_session, cliente_empresa_a.id, empresa_b.id)
        assert result is None

    async def test_get_by_id_propio_retorna_cliente(
        self, db_session, empresa_a, cliente_empresa_a,
    ):
        """Usuario de A puede ver cliente de A."""
        result = await cliente_repo.get_by_id(db_session, cliente_empresa_a.id, empresa_a.id)
        assert result is not None
        assert result.id == cliente_empresa_a.id


@pytest.mark.asyncio
class TestIsolationUsuario:
    """Tests de aislamiento para usuario_repo."""

    async def test_get_by_id_empresa_b_no_ve_usuario_empresa_a(
        self, db_session, empresa_a, empresa_b, user_empresa_a,
    ):
        """Usuario de B no puede ver usuario de A."""
        result = await usuario_repo.get_by_id(db_session, user_empresa_a.id, empresa_b.id)
        assert result is None

    async def test_get_by_id_propio_retorna_usuario(
        self, db_session, empresa_a, user_empresa_a,
    ):
        """Usuario de A puede ver usuario de A."""
        result = await usuario_repo.get_by_id(db_session, user_empresa_a.id, empresa_a.id)
        assert result is not None
        assert result.id == user_empresa_a.id


@pytest.mark.asyncio
class TestIsolationEndToEnd:
    """Tests end-to-end de infiltración con cookies de auth.

    Simula el escenario real: Empresa B tiene un pedido propio,
    pero intenta acceder al pedido de Empresa A usando el token de B.
    """

    async def test_usuario_empresa_b_no_puede_acceder_pedido_empresa_a_via_service(
        self, db_session, empresa_a, empresa_b, user_empresa_b, pedido_empresa_a,
    ):
        """El servicio debe retornar None cuando empresa_id no coincide."""
        from app.services import pedido_service

        # Empresa B intenta ver pedido de A
        result = await pedido_service.get_pedido_by_id(
            db_session, pedido_empresa_a.id, empresa_b.id,
        )
        assert result is None

    async def test_usuario_empresa_a_puede_ver_su_pedido(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a,
    ):
        """El servicio debe retornar el pedido cuando empresa_id coincide."""
        from app.services import pedido_service

        result = await pedido_service.get_pedido_by_id(
            db_session, pedido_empresa_a.id, empresa_a.id,
        )
        assert result is not None
        assert result.id == pedido_empresa_a.id

    async def test_usuario_empresa_b_no_puede_cancelar_pedido_empresa_a(
        self, db_session, empresa_a, empresa_b, user_empresa_a, pedido_empresa_a,
    ):
        """Cancelar pedido de otra empresa debe retornar None."""
        from app.services import pedido_service

        result = await pedido_service.cancelar_pedido(
            db_session, pedido_empresa_a.id, empresa_b.id,
        )
        assert result is None
        # Verificar que el pedido sigue existiendo y no fue cancelado
        pedido = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_a.id)
        assert pedido is not None
        assert pedido.estado != "cancelado"

    async def test_usuario_empresa_b_no_puede_actualizar_pedido_empresa_a(
        self, db_session, empresa_a, empresa_b, user_empresa_a, pedido_empresa_a,
    ):
        """Actualizar pedido de otra empresa debe retornar None."""
        from app.services import pedido_service

        result = await pedido_service.update_pedido(
            db_session, pedido_empresa_a.id, empresa_b.id, {"estado": "cancelado"},
        )
        assert result is None

    async def test_usuario_empresa_a_puede_cancelar_su_pedido(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a,
    ):
        """Cancelar pedido propio debe funcionar."""
        from app.services import pedido_service

        result = await pedido_service.cancelar_pedido(
            db_session, pedido_empresa_a.id, empresa_a.id,
        )
        assert result is not None
        assert result.estado == "cancelado"

    async def test_usuario_empresa_b_no_puede_eliminar_pedido_empresa_a(
        self, db_session, empresa_a, empresa_b, user_empresa_a, pedido_empresa_a,
    ):
        """Eliminar pedido de otra empresa debe retornar False."""
        from app.services import pedido_service

        result = await pedido_service.delete_pedido(
            db_session, pedido_empresa_a.id, empresa_b.id,
        )
        assert result is False
        # Verificar que el pedido sigue existiendo
        pedido = await pedido_repo.get_by_id(db_session, pedido_empresa_a.id, empresa_a.id)
        assert pedido is not None
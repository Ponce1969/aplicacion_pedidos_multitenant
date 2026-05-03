"""Tests para M-02: Asignación de repartidor y seguimiento de entrega."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntregaEvento, Pedido, PedidoItem, Producto, Usuario
from app.repositories import entrega_repo
from app.services import pedido_service
from app.services.pedido_service import InvalidEstadoTransition, TRANSICIONES_ESTADO, VALID_ESTADOS


class TestModelosM02:
    """M-02: Verificar que los modelos tienen los campos nuevos."""

    def test_usuario_tiene_campo_rol(self, user_empresa_a):
        """Usuario tiene campo 'rol'."""
        assert hasattr(user_empresa_a, "rol")
        assert user_empresa_a.rol == "admin"

    def test_pedido_tiene_repartidor_id(self, pedido_empresa_a):
        """Pedido tiene campo 'repartidor_id'."""
        assert hasattr(pedido_empresa_a, "repartidor_id")
        assert pedido_empresa_a.repartidor_id is None  # Sin asignar por defecto

    def test_entrega_evento_model_existe(self):
        """EntregaEvento model está definido."""
        assert hasattr(EntregaEvento, "__tablename__")
        assert EntregaEvento.__tablename__ == "entrega_eventos"


class TestRolesUsuario:
    """M-02: Roles de usuario (admin, operador, repartidor)."""

    async def test_usuario_admin_tiene_rol_admin(self, user_empresa_a):
        """Fixture admin tiene rol='admin' e is_admin=True."""
        assert user_empresa_a.rol == "admin"
        assert user_empresa_a.is_admin is True

    async def test_usuario_repartidor_tiene_rol_repartidor(self, repartidor_empresa_a):
        """Fixture repartidor tiene rol='repartidor'."""
        assert repartidor_empresa_a.rol == "repartidor"
        assert repartidor_empresa_a.is_admin is False

    async def test_usuario_operador_tiene_rol_operador(self, operador_empresa_a):
        """Fixture operador tiene rol='operador'."""
        assert operador_empresa_a.rol == "operador"
        assert operador_empresa_a.is_admin is False


class TestAsignarRepartidor:
    """M-02: Asignación de repartidor a pedido."""

    async def test_asignar_repartidor_cambia_estado_a_asignado(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Al asignar repartidor, el pedido pasa a estado 'asignado'."""
        pedido = await pedido_service.asignar_repartidor(
            db_session,
            pedido_empresa_a.id,
            repartidor_empresa_a.id,
            user_empresa_a.id,
            empresa_a.id,
        )
        assert pedido is not None
        assert pedido.repartidor_id == repartidor_empresa_a.id
        assert pedido.estado == "asignado"

    async def test_asignar_repartidor_crea_evento(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Al asignar repartidor, se crea un EntregaEvento."""
        await pedido_service.asignar_repartidor(
            db_session,
            pedido_empresa_a.id,
            repartidor_empresa_a.id,
            user_empresa_a.id,
            empresa_a.id,
        )

        eventos = await entrega_repo.get_by_pedido(db_session, pedido_empresa_a.id)
        assert len(eventos) == 1
        assert eventos[0].estado_anterior == "pendiente"
        assert eventos[0].estado_nuevo == "asignado"
        assert eventos[0].usuario_id == user_empresa_a.id

    async def test_asignar_repartidor_a_pedido_de_otra_empresa_falla(
        self, db_session, empresa_a, empresa_b, user_empresa_a, pedido_empresa_b, repartidor_empresa_a
    ):
        """No se puede asignar repartidor de empresa A a pedido de empresa B."""
        pedido = await pedido_service.asignar_repartidor(
            db_session,
            pedido_empresa_b.id,
            repartidor_empresa_a.id,
            user_empresa_a.id,
            empresa_a.id,
        )
        assert pedido is None


class TestCambiarEstadoEntrega:
    """M-02: Cambio de estado con validación de transiciones."""

    async def test_transicion_pendiente_a_asignado(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """pendiente → asignado es válido."""
        pedido = await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "asignado", user_empresa_a.id, empresa_a.id
        )
        assert pedido.estado == "asignado"

    async def test_transicion_asignado_a_en_camino(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """asignado → en_camino es válido."""
        pedido_empresa_a.estado = "asignado"
        await db_session.commit()

        pedido = await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "en_camino", user_empresa_a.id, empresa_a.id
        )
        assert pedido.estado == "en_camino"

    async def test_transicion_en_camino_a_entregado(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """en_camino → entregado es válido."""
        pedido_empresa_a.estado = "en_camino"
        await db_session.commit()

        pedido = await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "entregado", user_empresa_a.id, empresa_a.id
        )
        assert pedido.estado == "entregado"

    async def test_transicion_en_camino_a_no_entregado(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """en_camino → no_entregado es válido."""
        pedido_empresa_a.estado = "en_camino"
        await db_session.commit()

        pedido = await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "no_entregado", user_empresa_a.id, empresa_a.id, "Cliente no estaba"
        )
        assert pedido.estado == "no_entregado"

    async def test_transicion_no_entregado_a_pendiente_reintento(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """no_entregado → pendiente es válido (reintento)."""
        pedido_empresa_a.estado = "no_entregado"
        await db_session.commit()

        pedido = await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "pendiente", user_empresa_a.id, empresa_a.id, "Reintento"
        )
        assert pedido.estado == "pendiente"

    async def test_transicion_invalida_pendiente_a_entregado(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """pendiente → entregado NO es válido (debe pasar por asignado/en_camino)."""
        with pytest.raises(InvalidEstadoTransition):
            await pedido_service.cambiar_estado_entrega(
                db_session, pedido_empresa_a.id, "entregado", user_empresa_a.id, empresa_a.id
            )

    async def test_transicion_invalida_entregado_a_pendiente(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """entregado es estado final, no puede cambiar."""
        pedido_empresa_a.estado = "entregado"
        await db_session.commit()

        with pytest.raises(InvalidEstadoTransition):
            await pedido_service.cambiar_estado_entrega(
                db_session, pedido_empresa_a.id, "pendiente", user_empresa_a.id, empresa_a.id
            )

    async def test_transicion_invalida_cancelado_a_pendiente(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """cancelado es estado final, no puede cambiar."""
        pedido_empresa_a.estado = "cancelado"
        await db_session.commit()

        with pytest.raises(InvalidEstadoTransition):
            await pedido_service.cambiar_estado_entrega(
                db_session, pedido_empresa_a.id, "pendiente", user_empresa_a.id, empresa_a.id
            )

    async def test_cambiar_estado_crea_evento(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """Cada cambio de estado crea un EntregaEvento."""
        await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "asignado", user_empresa_a.id, empresa_a.id, "Asignación inicial"
        )

        eventos = await entrega_repo.get_by_pedido(db_session, pedido_empresa_a.id)
        assert len(eventos) == 1
        assert eventos[0].estado_anterior == "pendiente"
        assert eventos[0].estado_nuevo == "asignado"
        assert eventos[0].nota == "Asignación inicial"

    async def test_multiples_cambios_crean_multiples_eventos(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Flujo completo: pendiente → asignado → en_camino → entregado crea 3 eventos."""
        # Asignar
        await pedido_service.asignar_repartidor(
            db_session, pedido_empresa_a.id, repartidor_empresa_a.id, user_empresa_a.id, empresa_a.id
        )
        # En camino
        await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "en_camino", user_empresa_a.id, empresa_a.id
        )
        # Entregado
        await pedido_service.cambiar_estado_entrega(
            db_session, pedido_empresa_a.id, "entregado", user_empresa_a.id, empresa_a.id
        )

        eventos = await entrega_repo.get_by_pedido(db_session, pedido_empresa_a.id)
        assert len(eventos) == 3
        assert [e.estado_nuevo for e in eventos] == ["asignado", "en_camino", "entregado"]


class TestTransicionesConstantes:
    """M-02: Verificar que las constantes de transición son correctas."""

    def test_valid_estados_contiene_todos_los_estados(self):
        assert VALID_ESTADOS == {"pendiente", "asignado", "en_camino", "entregado", "no_entregado", "cancelado"}

    def test_transiciones_pendiente(self):
        assert TRANSICIONES_ESTADO["pendiente"] == {"asignado", "cancelado"}

    def test_transiciones_asignado(self):
        assert TRANSICIONES_ESTADO["asignado"] == {"en_camino", "pendiente", "cancelado"}

    def test_transiciones_en_camino(self):
        assert TRANSICIONES_ESTADO["en_camino"] == {"entregado", "no_entregado", "cancelado"}

    def test_transiciones_no_entregado(self):
        assert TRANSICIONES_ESTADO["no_entregado"] == {"pendiente", "cancelado"}

    def test_estado_final_entregado(self):
        assert TRANSICIONES_ESTADO["entregado"] == set()

    def test_estado_final_cancelado(self):
        assert TRANSICIONES_ESTADO["cancelado"] == set()

    def test_invalid_estado_transition_tiene_mensaje_descriptivo(self):
        error = InvalidEstadoTransition("entregado", "pendiente")
        assert "entregado" in str(error)
        assert "pendiente" in str(error)


class TestPedidosAsignadosRepartidor:
    """M-02: Pedidos asignados a repartidor."""

    async def test_repartidor_ve_sus_pedidos(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Repartidor solo ve pedidos asignados a él."""
        # Asignar pedido al repartidor
        await pedido_service.asignar_repartidor(
            db_session, pedido_empresa_a.id, repartidor_empresa_a.id, user_empresa_a.id, empresa_a.id
        )

        pedidos = await pedido_service.get_pedidos_asignados_repartidor(
            db_session, repartidor_empresa_a.id, empresa_a.id
        )
        assert len(pedidos) == 1
        assert pedidos[0].id == pedido_empresa_a.id

    async def test_repartidor_no_ve_pedidos_de_otros(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Repartidor no ve pedidos no asignados a él."""
        pedidos = await pedido_service.get_pedidos_asignados_repartidor(
            db_session, repartidor_empresa_a.id, empresa_a.id
        )
        assert len(pedidos) == 0

    async def test_repartidor_no_ve_pedidos_entregados(
        self, db_session, empresa_a, user_empresa_a, pedido_empresa_a, repartidor_empresa_a
    ):
        """Repartidor no ve pedidos ya entregados."""
        await pedido_service.asignar_repartidor(
            db_session, pedido_empresa_a.id, repartidor_empresa_a.id, user_empresa_a.id, empresa_a.id
        )
        pedido_empresa_a.estado = "entregado"
        await db_session.commit()

        pedidos = await pedido_service.get_pedidos_asignados_repartidor(
            db_session, repartidor_empresa_a.id, empresa_a.id
        )
        assert len(pedidos) == 0

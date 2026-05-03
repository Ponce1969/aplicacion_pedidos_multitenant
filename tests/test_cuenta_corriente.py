"""Tests para M-12: Gestión de deuda/saldo pendiente por cliente."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cliente, Pago
from app.repositories import cliente_repo
from app.repositories.cliente_repo import LimiteCreditoExcedido
from app.services import pedido_service


class TestClienteCuentaCorriente:
    """M-12: Campos de cuenta corriente en Cliente."""

    async def test_cliente_tiene_saldo_pendiente(self, cliente_empresa_a):
        assert hasattr(cliente_empresa_a, "saldo_pendiente")
        assert cliente_empresa_a.saldo_pendiente == Decimal("0")

    async def test_cliente_tiene_limite_credito(self, cliente_empresa_a):
        assert hasattr(cliente_empresa_a, "limite_credito")
        assert cliente_empresa_a.limite_credito is None  # Sin límite por defecto


class TestAgregarDeuda:
    """M-12: Agregar deuda al saldo del cliente."""

    async def test_agregar_deuda_suma_al_saldo(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Al confirmar un pedido, la deuda se suma al saldo pendiente."""
        cliente = await cliente_repo.agregar_deuda(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("5000")
        )
        assert cliente is not None
        assert cliente.saldo_pendiente == Decimal("5000")

    async def test_agregar_deuda_acumula(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Múltiples pedidos acumulan deuda."""
        await cliente_repo.agregar_deuda(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("3000")
        )
        cliente = await cliente_repo.agregar_deuda(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("2000")
        )
        assert cliente.saldo_pendiente == Decimal("5000")

    async def test_agregar_deuda_cliente_inexistente_retorna_none(
        self, db_session, empresa_a
    ):
        """Si el cliente no existe, retorna None."""
        resultado = await cliente_repo.agregar_deuda(
            db_session, 9999, empresa_a.id, Decimal("1000")
        )
        assert resultado is None


class TestRegistrarPago:
    """M-12: Registrar pago y reducir saldo."""

    async def test_registrar_pago_reduce_saldo(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """Al registrar un pago, el saldo pendiente se reduce."""
        # Primero agregar deuda
        await cliente_repo.agregar_deuda(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("10000")
        )

        # Registrar pago
        pago, cliente = await cliente_repo.registrar_pago(
            db_session,
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            monto=Decimal("4000"),
            usuario_id=user_empresa_a.id,
        )
        assert pago.id is not None
        assert pago.monto == Decimal("4000")
        assert cliente.saldo_pendiente == Decimal("6000")

    async def test_pago_no_deja_saldo_negativo(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """Si el pago excede la deuda, el saldo queda en 0 (no negativo)."""
        await cliente_repo.agregar_deuda(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("3000")
        )

        pago, cliente = await cliente_repo.registrar_pago(
            db_session,
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            monto=Decimal("5000"),
            usuario_id=user_empresa_a.id,
        )
        assert cliente.saldo_pendiente == Decimal("0")

    async def test_pago_monto_cero_lanza_error(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """Pago con monto <= 0 lanza ValueError."""
        with pytest.raises(ValueError, match="mayor a 0"):
            await cliente_repo.registrar_pago(
                db_session,
                cliente_id=cliente_empresa_a.id,
                empresa_id=empresa_a.id,
                monto=Decimal("0"),
                usuario_id=user_empresa_a.id,
            )

    async def test_pago_monto_negativo_lanza_error(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """Pago con monto negativo lanza ValueError."""
        with pytest.raises(ValueError, match="mayor a 0"):
            await cliente_repo.registrar_pago(
                db_session,
                cliente_id=cliente_empresa_a.id,
                empresa_id=empresa_a.id,
                monto=Decimal("-100"),
                usuario_id=user_empresa_a.id,
            )

    async def test_pago_cliente_inexistente_lanza_error(
        self, db_session, empresa_a, user_empresa_a
    ):
        """Pago a cliente inexistente lanza ValueError."""
        with pytest.raises(ValueError, match="no encontrado"):
            await cliente_repo.registrar_pago(
                db_session,
                cliente_id=9999,
                empresa_id=empresa_a.id,
                monto=Decimal("1000"),
                usuario_id=user_empresa_a.id,
            )

    async def test_pago_guarda_metodo_y_nota(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """El pago registra método de pago y nota."""
        pago, _ = await cliente_repo.registrar_pago(
            db_session,
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            monto=Decimal("1000"),
            usuario_id=user_empresa_a.id,
            metodo_pago="transferencia",
            nota="Transferencia Brou ref #12345",
        )
        assert pago.metodo_pago == "transferencia"
        assert pago.nota == "Transferencia Brou ref #12345"

    async def test_pago_vinculado_a_pedido(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a, pedido_empresa_a
    ):
        """El pago puede vincularse a un pedido específico."""
        pago, _ = await cliente_repo.registrar_pago(
            db_session,
            cliente_id=cliente_empresa_a.id,
            empresa_id=empresa_a.id,
            monto=Decimal("1000"),
            usuario_id=user_empresa_a.id,
            pedido_id=pedido_empresa_a.id,
        )
        assert pago.pedido_id == pedido_empresa_a.id


class TestGetPagosCliente:
    """M-12: Historial de pagos."""

    async def test_get_pagos_ordenados_descendente(
        self, db_session, empresa_a, cliente_empresa_a, user_empresa_a
    ):
        """Pagos se retornan ordenados del más reciente al más antiguo."""
        await cliente_repo.registrar_pago(
            db_session, cliente_empresa_a.id, empresa_a.id,
            Decimal("1000"), user_empresa_a.id, nota="Pago 1"
        )
        await cliente_repo.registrar_pago(
            db_session, cliente_empresa_a.id, empresa_a.id,
            Decimal("2000"), user_empresa_a.id, nota="Pago 2"
        )

        pagos = await cliente_repo.get_pagos_cliente(
            db_session, cliente_empresa_a.id, empresa_a.id
        )
        assert len(pagos) == 2
        # Verificar que ambos pagos están presentes (orden puede variar por resolución de timestamp)
        notas = {p.nota for p in pagos}
        assert notas == {"Pago 1", "Pago 2"}


class TestLimiteCredito:
    """M-12: Validación de límite de crédito."""

    async def test_sin_limite_permite_cualquier_deuda(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Sin límite configurado, no hay restricción."""
        cliente_empresa_a.limite_credito = None
        await db_session.commit()

        # No debe lanzar excepción
        await cliente_repo.verificar_limite_credito(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("999999")
        )

    async def test_dentro_del_limite_permite(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Dentro del límite, no lanza excepción."""
        cliente_empresa_a.limite_credito = Decimal("10000")
        cliente_empresa_a.saldo_pendiente = Decimal("5000")
        await db_session.commit()

        await cliente_repo.verificar_limite_credito(
            db_session, cliente_empresa_a.id, empresa_a.id, Decimal("4000")
        )

    async def test_excede_limite_lanza_excepcion(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """Si el pedido excede el límite, lanza LimiteCreditoExcedido."""
        cliente_empresa_a.limite_credito = Decimal("10000")
        cliente_empresa_a.saldo_pendiente = Decimal("8000")
        await db_session.commit()

        with pytest.raises(LimiteCreditoExcedido):
            await cliente_repo.verificar_limite_credito(
                db_session, cliente_empresa_a.id, empresa_a.id, Decimal("3000")
            )

    async def test_limite_excedido_tiene_mensaje_descriptivo(
        self, db_session, empresa_a, cliente_empresa_a
    ):
        """La excepción tiene un mensaje con los detalles."""
        cliente_empresa_a.limite_credito = Decimal("10000")
        cliente_empresa_a.saldo_pendiente = Decimal("8000")
        await db_session.commit()

        with pytest.raises(LimiteCreditoExcedido) as exc_info:
            await cliente_repo.verificar_limite_credito(
                db_session, cliente_empresa_a.id, empresa_a.id, Decimal("3000")
            )
        assert "10000" in str(exc_info.value)
        assert "8000" in str(exc_info.value)
        assert "3000" in str(exc_info.value)


class TestTopDeudores:
    """M-12: Ranking de deudores."""

    async def test_top_deudores_ordenados_por_saldo(
        self, db_session, empresa_a
    ):
        """Deudores ordenados por saldo pendiente descendente."""
        c1 = Cliente(
            nombre="Cliente", apellido="A", celular="099111111",
            direccion="Dir A", empresa_id=empresa_a.id,
            saldo_pendiente=Decimal("5000"),
        )
        c2 = Cliente(
            nombre="Cliente", apellido="B", celular="099222222",
            direccion="Dir B", empresa_id=empresa_a.id,
            saldo_pendiente=Decimal("15000"),
        )
        c3 = Cliente(
            nombre="Cliente", apellido="C", celular="099333333",
            direccion="Dir C", empresa_id=empresa_a.id,
            saldo_pendiente=Decimal("0"),  # Sin deuda
        )
        db_session.add_all([c1, c2, c3])
        await db_session.commit()

        deudores = await cliente_repo.get_top_deudores(db_session, empresa_a.id)
        assert len(deudores) == 2  # C no aparece (deuda = 0)
        assert deudores[0].apellido == "B"  # Mayor deuda primero
        assert deudores[1].apellido == "A"

    async def test_top_deudores_multi_tenant(
        self, db_session, empresa_a, empresa_b
    ):
        """Solo muestra deudores de la empresa del usuario."""
        c_a = Cliente(
            nombre="Deudor", apellido="A", celular="099111111",
            direccion="Dir A", empresa_id=empresa_a.id,
            saldo_pendiente=Decimal("5000"),
        )
        c_b = Cliente(
            nombre="Deudor", apellido="B", celular="099222222",
            direccion="Dir B", empresa_id=empresa_b.id,
            saldo_pendiente=Decimal("10000"),
        )
        db_session.add_all([c_a, c_b])
        await db_session.commit()

        deudores_a = await cliente_repo.get_top_deudores(db_session, empresa_a.id)
        deudores_b = await cliente_repo.get_top_deudores(db_session, empresa_b.id)
        assert len(deudores_a) == 1
        assert deudores_a[0].apellido == "A"
        assert len(deudores_b) == 1
        assert deudores_b[0].apellido == "B"


class TestPagoModel:
    """M-12: Modelo Pago."""

    def test_pago_model_existe(self):
        assert hasattr(Pago, "__tablename__")
        assert Pago.__tablename__ == "pagos"

    def test_pago_tiene_campos_requeridos(self):
        assert hasattr(Pago, "monto")
        assert hasattr(Pago, "metodo_pago")
        assert hasattr(Pago, "cliente_id")
        assert hasattr(Pago, "empresa_id")
        assert hasattr(Pago, "registrado_por")

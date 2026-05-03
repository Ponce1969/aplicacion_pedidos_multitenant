"""Tests para M-03: Descuento automático de stock."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Empresa, Pedido, PedidoItem, Producto, Usuario
from app.repositories.producto_repo import InsufficientStockError
from app.services import pedido_service


class TestStockDescuentoAlCrearPedido:
    """M-03: El stock se descuenta al crear un pedido con items."""

    async def test_stock_se_descuenta_al_crear_pedido(
        self, client, user_empresa_a, empresa_a, db_session
    ):
        """Al crear un pedido, el stock de cada producto se descuenta."""
        producto = Producto(
            nombre="Arena bolsa",
            sku="ARENA-25",
            precio_base=Decimal("200.00"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("10"),
        )
        db_session.add(producto)
        await db_session.commit()
        await db_session.refresh(producto)

        await client.post(
            "/api/login",
            data={"email": user_empresa_a.email, "password": "Test123!"},
        )

        items = [
            {
                "descripcion": "Arena bolsa",
                "cantidad": 3,
                "precio_unitario": 200.0,
                "producto_id": producto.id,
            }
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Juan",
                "apellido": "Perez",
                "celular": "099123456",
                "direccion": "Av. Italia 1234",
                "hora_entrega": "15:30",
                "fecha_entrega": (date.today() + timedelta(days=1)).isoformat(),
                "pedido_detalle": "Arena - 3",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code == 200

        # Verificar que el stock se descontó
        await db_session.refresh(producto)
        assert producto.stock == Decimal("7")  # 10 - 3

    async def test_stock_suficiente_rechaza_pedido(
        self, client, user_empresa_a, empresa_a, db_session
    ):
        """Si no hay stock suficiente, el pedido no se crea (422)."""
        producto = Producto(
            nombre="Cemento",
            sku="CEM-50",
            precio_base=Decimal("500.00"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("2"),
        )
        db_session.add(producto)
        await db_session.commit()
        await db_session.refresh(producto)

        await client.post(
            "/api/login",
            data={"email": user_empresa_a.email, "password": "Test123!"},
        )

        items = [
            {
                "descripcion": "Cemento",
                "cantidad": 5,
                "precio_unitario": 500.0,
                "producto_id": producto.id,
            }
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Juan",
                "apellido": "Perez",
                "celular": "099123456",
                "direccion": "Av. Italia 1234",
                "hora_entrega": "15:30",
                "fecha_entrega": (date.today() + timedelta(days=1)).isoformat(),
                "pedido_detalle": "Cemento - 5",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code == 422

        # Verificar que el stock NO cambió
        await db_session.refresh(producto)
        assert producto.stock == Decimal("2")


class TestStockNoneSinControl:
    """M-03: Productos con stock=None no tienen validación de stock."""

    async def test_producto_sin_stock_permite_crear_pedido(
        self, client, user_empresa_a, empresa_a, producto_empresa_a, db_session
    ):
        """Producto con stock=None permite pedidos de cualquier cantidad."""
        assert producto_empresa_a.stock is None

        await client.post(
            "/api/login",
            data={"email": user_empresa_a.email, "password": "Test123!"},
        )

        items = [
            {
                "descripcion": producto_empresa_a.nombre,
                "cantidad": 999,
                "precio_unitario": float(producto_empresa_a.precio_base),
                "producto_id": producto_empresa_a.id,
            }
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Juan",
                "apellido": "Perez",
                "celular": "099123456",
                "direccion": "Av. Italia 1234",
                "hora_entrega": "15:30",
                "fecha_entrega": (date.today() + timedelta(days=1)).isoformat(),
                "pedido_detalle": "Test",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code == 200

        # Stock sigue siendo None (no se modificó)
        await db_session.refresh(producto_empresa_a)
        assert producto_empresa_a.stock is None


class TestStockRestauracionAlCancelar:
    """M-03: El stock se restaura al cancelar un pedido."""

    async def test_cancelar_pedido_restaura_stock(self, db_session, empresa_a, user_empresa_a):
        """Al cancelar un pedido, el stock de cada producto se restaura."""
        producto = Producto(
            nombre="Ladrillo",
            sku="LAD-100",
            precio_base=Decimal("100.00"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("20"),
        )
        db_session.add(producto)
        await db_session.commit()
        await db_session.refresh(producto)

        # Crear pedido con 5 unidades (stock pasa a 15)
        pedido = Pedido(
            nombre="Test",
            apellido="Cancel",
            celular="099111111",
            direccion="Dir",
            hora_entrega="10:00",
            pedido_detalle="Ladrillo - 5",
            total=Decimal("500"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
            estado="pendiente",
        )
        pedido.items.append(
            PedidoItem(
                descripcion="Ladrillo",
                cantidad=Decimal("5"),
                precio_unitario=Decimal("100"),
                subtotal=Decimal("500"),
                producto_id=producto.id,
            )
        )
        db_session.add(pedido)
        await db_session.commit()
        await db_session.refresh(pedido)

        # Simular descuento de stock
        producto.stock = Decimal("15")
        await db_session.commit()

        # Cancelar pedido
        resultado = await pedido_service.cancelar_pedido(db_session, pedido.id, empresa_a.id)
        assert resultado is not None
        assert resultado.estado == "cancelado"

        # Verificar stock restaurado
        await db_session.refresh(producto)
        assert producto.stock == Decimal("20")  # 15 + 5

    async def test_cancelar_pedido_sin_stock_no_modifica(
        self, db_session, empresa_a, user_empresa_a, producto_empresa_a
    ):
        """Cancelar pedido de producto sin control de stock no falla."""
        pedido = Pedido(
            nombre="Test",
            apellido="Cancel",
            celular="099111111",
            direccion="Dir",
            hora_entrega="10:00",
            pedido_detalle="Test",
            total=Decimal("500"),
            empresa_id=empresa_a.id,
            usuario_id=user_empresa_a.id,
            estado="pendiente",
        )
        pedido.items.append(
            PedidoItem(
                descripcion="Test",
                cantidad=Decimal("5"),
                precio_unitario=Decimal("100"),
                subtotal=Decimal("500"),
                producto_id=producto_empresa_a.id,
            )
        )
        db_session.add(pedido)
        await db_session.commit()
        await db_session.refresh(pedido)

        resultado = await pedido_service.cancelar_pedido(db_session, pedido.id, empresa_a.id)
        assert resultado is not None
        assert resultado.estado == "cancelado"

        # Stock sigue siendo None
        await db_session.refresh(producto_empresa_a)
        assert producto_empresa_a.stock is None


class TestStockAtomicidad:
    """M-03: El descuento de stock es atómico."""

    async def test_falla_un_item_ninguno_se_descuenta(
        self, client, user_empresa_a, empresa_a, db_session
    ):
        """Si un producto no tiene stock, ningún producto se descuenta."""
        prod_a = Producto(
            nombre="Prod A",
            sku="PA",
            precio_base=Decimal("100"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("10"),
        )
        prod_b = Producto(
            nombre="Prod B",
            sku="PB",
            precio_base=Decimal("200"),
            empresa_id=empresa_a.id,
            is_active=True,
            stock=Decimal("1"),  # Solo 1 disponible
        )
        db_session.add_all([prod_a, prod_b])
        await db_session.commit()
        await db_session.refresh(prod_a)
        await db_session.refresh(prod_b)

        await client.post(
            "/api/login",
            data={"email": user_empresa_a.email, "password": "Test123!"},
        )

        items = [
            {"descripcion": "Prod A", "cantidad": 3, "precio_unitario": 100, "producto_id": prod_a.id},
            {"descripcion": "Prod B", "cantidad": 5, "precio_unitario": 200, "producto_id": prod_b.id},
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Juan",
                "apellido": "Perez",
                "celular": "099123456",
                "direccion": "Av. Italia 1234",
                "hora_entrega": "15:30",
                "fecha_entrega": (date.today() + timedelta(days=1)).isoformat(),
                "pedido_detalle": "Test",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code == 422

        # Ningún stock se descuenta
        await db_session.refresh(prod_a)
        await db_session.refresh(prod_b)
        assert prod_a.stock == Decimal("10")
        assert prod_b.stock == Decimal("1")


class TestInsufficientStockError:
    """M-03: Excepción custom para stock insuficiente."""

    def test_error_message_contains_details(self):
        error = InsufficientStockError("Cemento", Decimal("2"), Decimal("5"))
        assert "Cemento" in str(error)
        assert "2" in str(error)
        assert "5" in str(error)
        assert error.producto_nombre == "Cemento"
        assert error.stock_disponible == Decimal("2")
        assert error.cantidad_solicitada == Decimal("5")

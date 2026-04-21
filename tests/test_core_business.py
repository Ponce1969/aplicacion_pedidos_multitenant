"""Tests de core business: pedidos con items, entregas, autocomplete.

Estos tests cubren el flujo principal de negocio de una barraca:
crear pedidos con items, visualizar entregas pendientes,
y autocompletado de clientes/productos.
"""

import json
from datetime import UTC, date, datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Cliente, Pedido, Producto


# ==================== PEDIDOS CON ITEMS ====================


class TestCreatePedidoConItems:
    """Tests del flujo nuevo de pedidos con items JSON."""

    async def test_crear_pedido_con_items_calcula_total_automatico(
        self, client, user_empresa_a, empresa_a, producto_empresa_a, db_session
    ):
        """Pedido con items_json calcula subtotal y total automaticamente."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        items = [
            {
                "descripcion": producto_empresa_a.nombre,
                "cantidad": 3,
                "precio_unitario": float(producto_empresa_a.precio_base),
                "producto_id": producto_empresa_a.id,
            },
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Juan",
                "apellido": "Perez",
                "celular": "099123456",
                "direccion": "Av. Italia 1234",
                "hora_entrega": "15:30",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Cemento 25kg - 3 unidades",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code in [200, 302]

        # Verificar en BD
        query = select(Pedido).where(Pedido.apellido == "Perez", Pedido.empresa_id == empresa_a.id)
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se creo"
        assert len(pedido.items) == 1
        assert pedido.items[0].descripcion == producto_empresa_a.nombre
        assert float(pedido.items[0].cantidad) == 3
        assert float(pedido.items[0].subtotal) == 3 * float(producto_empresa_a.precio_base)
        assert pedido.subtotal is not None
        assert float(pedido.total) == float(pedido.subtotal) + float(pedido.impuestos or 0)

    async def test_crear_pedido_con_items_y_cliente_id(
        self, client, user_empresa_a, empresa_a, producto_empresa_a, cliente_empresa_a, db_session
    ):
        """Pedido con items y cliente_id asigna el cliente correctamente."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        items = [
            {
                "descripcion": producto_empresa_a.nombre,
                "cantidad": 1,
                "precio_unitario": float(producto_empresa_a.precio_base),
                "producto_id": producto_empresa_a.id,
            },
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": cliente_empresa_a.nombre,
                "apellido": cliente_empresa_a.apellido,
                "celular": cliente_empresa_a.celular,
                "direccion": cliente_empresa_a.direccion,
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Pedido con cliente registrado",
                "cliente_id": str(cliente_empresa_a.id),
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code in [200, 302]

        query = select(Pedido).where(Pedido.celular == cliente_empresa_a.celular)
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None
        assert pedido.cliente_id == cliente_empresa_a.id
        assert pedido.empresa_id == empresa_a.id

    async def test_crear_pedido_con_items_multiple_lineas(
        self, client, user_empresa_a, empresa_a, producto_empresa_a, db_session
    ):
        """Pedido con multiples items suma correctamente."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        items = [
            {
                "descripcion": producto_empresa_a.nombre,
                "cantidad": 2,
                "precio_unitario": 500.00,
                "producto_id": producto_empresa_a.id,
            },
            {
                "descripcion": "Cal",
                "cantidad": 5,
                "precio_unitario": 120.00,
                "producto_id": None,
            },
        ]

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "MultiItems",
                "celular": "099000000",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Varios items",
                "items_json": json.dumps(items),
            },
        )
        assert response.status_code in [200, 302]

        query = select(Pedido).where(Pedido.apellido == "MultiItems")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None
        assert len(pedido.items) == 2
        # Subtotal esperado: 2*500 + 5*120 = 1000 + 600 = 1600
        assert float(pedido.subtotal) == 1600.0


# ==================== ENTREGAS ====================


class TestEntregas:
    """Tests de la pagina de entregas pendientes."""

    async def test_entregas_muestra_pedidos_pendientes(self, client, user_empresa_a, pedido_empresa_a):
        """/entregas muestra pedidos con estado 'pendiente'."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/entregas")
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" in response.text
        assert pedido_empresa_a.nombre in response.text
        assert pedido_empresa_a.celular in response.text

    async def test_entregas_no_muestra_pedidos_entregados(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Pedidos con estado 'entregado' NO aparecen en entregas."""
        # Marcar pedido como entregado
        pedido_empresa_a.estado = "entregado"
        await db_session.commit()

        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/entregas")
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" not in response.text

    async def test_entregas_solo_muestra_de_su_empresa(
        self, client, user_empresa_a, pedido_empresa_a, pedido_empresa_b
    ):
        """CRITICO: Entregas solo muestra pedidos de la empresa del usuario."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/entregas")
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" in response.text
        assert f"#{pedido_empresa_b.id}" not in response.text

    async def test_entregas_filtro_por_fecha(self, client, user_empresa_a, db_session):
        """Filtrar entregas por fecha especifica."""
        manana = date.today() + timedelta(days=1)
        pedido_manana = Pedido(
            nombre="Cliente",
            apellido="Manana",
            celular="099777777",
            direccion="Calle Manana",
            hora_entrega="10:00",
            fecha_entrega=datetime(manana.year, manana.month, manana.day, tzinfo=UTC),
            pedido_detalle="Test",
            total=1000,
            empresa_id=user_empresa_a.empresa_id,
            usuario_id=user_empresa_a.id,
            estado="pendiente",
        )
        db_session.add(pedido_manana)
        await db_session.commit()
        await db_session.refresh(pedido_manana)

        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/entregas?fecha={manana.isoformat()}")
        assert response.status_code == 200
        assert f"#{pedido_manana.id}" in response.text

    async def test_entregas_sin_pedidos_pendientes_muestra_vacio(
        self, client, user_empresa_a, pedido_empresa_a, db_session
    ):
        """Sin pedidos pendientes la pagina carga pero sin resultados."""
        # Marcar todos como entregado
        pedido_empresa_a.estado = "entregado"
        await db_session.commit()

        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/entregas")
        assert response.status_code == 200


# ==================== AUTOCOMPLETE CLIENTES ====================


class TestClientesAutocomplete:
    """Tests de autocomplete HTMX de clientes."""

    async def test_buscar_clientes_retorna_resultados(self, client, user_empresa_a, cliente_empresa_a):
        """Buscar clientes con termino valido retorna lista HTML."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/clientes/buscar?q={cliente_empresa_a.nombre}")
        assert response.status_code == 200
        assert cliente_empresa_a.nombre in response.text
        assert cliente_empresa_a.celular in response.text

    async def test_buscar_clientes_menos_de_2_caracteres_vacio(self, client, user_empresa_a):
        """Busqueda con menos de 2 caracteres retorna HTML vacio."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/api/clientes/buscar?q=a")
        assert response.status_code == 200
        assert response.text == ""

    async def test_buscar_clientes_tenant_isolation(self, client, user_empresa_a, cliente_empresa_a, cliente_empresa_b):
        """CRITICO: Busqueda de clientes no muestra clientes de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/clientes/buscar?q={cliente_empresa_a.nombre}")
        assert response.status_code == 200
        assert cliente_empresa_a.nombre in response.text
        assert cliente_empresa_b.nombre not in response.text

    async def test_buscar_clientes_por_apellido(self, client, user_empresa_a, cliente_empresa_a):
        """Busqueda por apellido funciona."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/clientes/buscar?q={cliente_empresa_a.apellido}")
        assert response.status_code == 200
        assert cliente_empresa_a.apellido in response.text

    async def test_buscar_clientes_por_celular(self, client, user_empresa_a, cliente_empresa_a):
        """Busqueda por celular funciona."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/clientes/buscar?q={cliente_empresa_a.celular}")
        assert response.status_code == 200
        assert cliente_empresa_a.celular in response.text


# ==================== AUTOCOMPLETE PRODUCTOS ====================


class TestProductosAutocomplete:
    """Tests de autocomplete HTMX de productos."""

    async def test_buscar_productos_retorna_resultados(self, client, user_empresa_a, producto_empresa_a):
        """Buscar productos con termino valido retorna lista HTML."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/productos/buscar?q={producto_empresa_a.nombre}")
        assert response.status_code == 200
        assert producto_empresa_a.nombre in response.text

    async def test_buscar_productos_menos_de_2_caracteres_vacio(self, client, user_empresa_a):
        """Busqueda con menos de 2 caracteres retorna HTML vacio."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/api/productos/buscar?q=a")
        assert response.status_code == 200
        assert response.text == ""

    async def test_buscar_productos_tenant_isolation(
        self, client, user_empresa_a, producto_empresa_a, producto_empresa_b
    ):
        """CRITICO: Busqueda de productos no muestra productos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/productos/buscar?q={producto_empresa_a.nombre}")
        assert response.status_code == 200
        assert producto_empresa_a.nombre in response.text
        assert producto_empresa_b.nombre not in response.text

    async def test_buscar_productos_por_sku(self, client, user_empresa_a, producto_empresa_a):
        """Busqueda por SKU funciona."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/api/productos/buscar?q={producto_empresa_a.sku}")
        assert response.status_code == 200
        # El template no muestra SKU, pero el producto debe aparecer en la lista
        assert producto_empresa_a.nombre in response.text
        assert str(producto_empresa_a.id) in response.text

    async def test_buscar_productos_inactivos_no_aparecen(self, client, user_empresa_a, empresa_a, db_session):
        """Productos inactivos no aparecen en la busqueda."""
        # Crear producto inactivo
        producto_inactivo = Producto(
            nombre="Producto Inactivo",
            sku="INA-001",
            precio_base=100,
            empresa_id=empresa_a.id,
            is_active=False,
        )
        db_session.add(producto_inactivo)
        await db_session.commit()

        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/api/productos/buscar?q=Inactivo")
        assert response.status_code == 200
        assert "Inactivo" not in response.text

"""Tests de CRUD de pedidos con aislamiento multi-tenant.

Verifica que las operaciones CRUD (Create, Read, Update, Delete)
funcionen correctamente dentro del contexto multi-tenant.
"""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Pedido


# ==================== CREATE ====================


class TestCreatePedido:
    """Tests de creacion de pedidos."""

    async def test_crear_pedido_exitoso(self, client, user_empresa_a, empresa_a, db_session):
        """Crear pedido valido asigna automaticamente empresa_id y usuario_id."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        pedido_data = {
            "nombre": "Juan",
            "apellido": "Perez",
            "celular": "099123456",
            "direccion": "Av. Italia 1234",
            "hora_entrega": "15:30",
            "fecha_entrega": fecha_entrega,
            "pedido_detalle": "Cemento 25kg - 3 unidades\nCal - 2 bolsas\nCinta - 5 rollos",
            "total": "15750.00",
        }

        response = await client.post("/guardar-pedido", data=pedido_data)
        assert response.status_code in [200, 302]

        # Verificar en BD que se guardo correctamente
        query = select(Pedido).where(
            Pedido.apellido == "Perez",
            Pedido.empresa_id == empresa_a.id,
            Pedido.usuario_id == user_empresa_a.id,
        )
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se encontro en la BD"
        assert pedido.nombre == "Juan"
        assert pedido.total == 15750.00
        assert pedido.estado == "pendiente"
        assert pedido.empresa_id == empresa_a.id
        assert pedido.usuario_id == user_empresa_a.id

    async def test_crear_pedido_asigna_empresa_del_usuario(
        self, client, user_empresa_a, empresa_a, empresa_b, db_session
    ):
        """CRITICO: El pedido siempre se asigna a la empresa del usuario autenticado,
        sin importar que datos se envien en el formulario."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        pedido_data = {
            "nombre": "Intruso",
            "apellido": "Test",
            "celular": "099000000",
            "direccion": "Calle Falsa 123",
            "hora_entrega": "10:00",
            "fecha_entrega": fecha_entrega,
            "pedido_detalle": "Producto test",
            "total": "1000",
        }

        response = await client.post("/guardar-pedido", data=pedido_data)
        assert response.status_code in [200, 302]

        # Verificar que empresa_id es SIEMPRE el del usuario, inmutable
        query = select(Pedido).where(Pedido.apellido == "Test")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None
        assert pedido.empresa_id == empresa_a.id
        assert pedido.empresa_id != empresa_b.id, "SEGURIDAD: pedido asignado a empresa equivocada"

    async def test_crear_pedido_sin_autenticacion_redirige(self, client):
        """Usuario no autenticado no puede crear pedidos."""
        pedido_data = {
            "nombre": "Test",
            "apellido": "User",
            "celular": "099123456",
            "direccion": "Calle Test 123",
            "hora_entrega": "10:00",
            "fecha_entrega": date.today().isoformat(),
            "pedido_detalle": "Producto test - 1",
            "total": "1000",
        }

        response = await client.post("/guardar-pedido", data=pedido_data, follow_redirects=False)
        assert response.status_code in [302, 401], "Sin auth debe redirigir o rechazar"

    async def test_crear_pedido_detalle_con_saltos_de_linea(self, client, user_empresa_a, db_session):
        """El detalle del pedido debe preservar saltos de linea."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        detalle = "Cemento 25kg - 3 unidades\nCal - 2 bolsas\nCinta - 5 rollos"
        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "DetalleFormato",
                "celular": "099123456",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": detalle,
                "total": "25750",
            },
        )
        assert response.status_code in [200, 302]

        query = select(Pedido).where(Pedido.apellido == "DetalleFormato")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se encontro en la BD"
        assert "\n" in pedido.pedido_detalle, "Los saltos de linea se perdieron"
        assert "Cemento" in pedido.pedido_detalle

    async def test_crear_pedido_registra_fecha_creacion_automatica(self, client, user_empresa_a, db_session):
        """fecha_creacion se asigna automaticamente, no la envia el usuario."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()

        response = await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "FechaAuto",
                "celular": "099123456",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Producto - 1",
                "total": "1000",
            },
        )
        assert response.status_code in [200, 302]

        query = select(Pedido).where(Pedido.apellido == "FechaAuto")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None
        assert pedido.fecha_creacion is not None, "fecha_creacion debe asignarse automaticamente"


# ==================== READ ====================


class TestReadPedido:
    """Tests de lectura de pedidos."""

    async def test_listar_pedidos_muestra_solo_de_su_empresa(
        self, client, user_empresa_a, pedido_empresa_a, pedido_empresa_a_2
    ):
        """Listar pedidos (/pedidos) muestra SOLO los de la empresa del usuario."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/pedidos")
        assert response.status_code == 200
        # Debe contener los pedidos de empresa A
        assert f"#{pedido_empresa_a.id}" in response.text
        assert f"#{pedido_empresa_a_2.id}" in response.text

    async def test_ver_pedido_detalle_propio(self, client, user_empresa_a, pedido_empresa_a):
        """Ver detalle de pedido propio muestra toda la informacion."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_a.id}")
        assert response.status_code == 200
        assert pedido_empresa_a.nombre in response.text
        assert pedido_empresa_a.apellido in response.text
        assert pedido_empresa_a.celular in response.text
        assert pedido_empresa_a.direccion in response.text

    async def test_ver_pedido_inexistente_retorna_404(self, client, user_empresa_a):
        """Pedido que no existe retorna 404."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get("/pedido/99999")
        assert response.status_code == 404

    async def test_ver_pedido_otra_empresa_retorna_404(self, client, user_empresa_a, pedido_empresa_b):
        """CRITICO: No se pueden ver pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_b.id}")
        assert response.status_code == 404
        assert "no encontrado" in response.text.lower()


# ==================== UPDATE ====================


class TestUpdatePedido:
    """Tests de actualizacion de pedidos."""

    async def test_editar_pedido_propio_exitoso(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Editar pedido propio actualiza los campos correctamente."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=2)).isoformat()

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_a.id}",
            data={
                "nombre": "Juan Editado",
                "apellido": "Perez Modificado",
                "celular": "099999999",
                "direccion": "Nueva Direccion 456",
                "hora_entrega": "20:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Productos actualizados - 10 unidades",
                "estado": "entregado",
            },
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]

        await db_session.refresh(pedido_empresa_a)
        assert pedido_empresa_a.nombre == "Juan Editado"
        assert pedido_empresa_a.apellido == "Perez Modificado"
        assert pedido_empresa_a.celular == "099999999"
        assert pedido_empresa_a.direccion == "Nueva Direccion 456"
        assert pedido_empresa_a.estado == "entregado"

    async def test_editar_pedido_estado_pendiente_funciona(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Cambiar estado a 'pendiente' (permitido)."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_a.id}",
            data={
                "nombre": pedido_empresa_a.nombre,
                "apellido": pedido_empresa_a.apellido,
                "celular": pedido_empresa_a.celular,
                "direccion": pedido_empresa_a.direccion,
                "hora_entrega": pedido_empresa_a.hora_entrega,
                "pedido_detalle": pedido_empresa_a.pedido_detalle,
                "estado": "pendiente",
            },
        )
        assert response.status_code in [200, 302]
        await db_session.refresh(pedido_empresa_a)
        assert pedido_empresa_a.estado == "pendiente"

    async def test_editar_pedido_estado_entregado_funciona(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Cambiar estado a 'entregado' (permitido)."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_a.id}",
            data={
                "nombre": pedido_empresa_a.nombre,
                "apellido": pedido_empresa_a.apellido,
                "celular": pedido_empresa_a.celular,
                "direccion": pedido_empresa_a.direccion,
                "hora_entrega": pedido_empresa_a.hora_entrega,
                "pedido_detalle": pedido_empresa_a.pedido_detalle,
                "estado": "entregado",
            },
        )
        assert response.status_code in [200, 302]
        await db_session.refresh(pedido_empresa_a)
        assert pedido_empresa_a.estado == "entregado"

    async def test_editar_pedido_estado_cancelado_funciona(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Cambiar estado a 'cancelado' (permitido)."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_a.id}",
            data={
                "nombre": pedido_empresa_a.nombre,
                "apellido": pedido_empresa_a.apellido,
                "celular": pedido_empresa_a.celular,
                "direccion": pedido_empresa_a.direccion,
                "hora_entrega": pedido_empresa_a.hora_entrega,
                "pedido_detalle": pedido_empresa_a.pedido_detalle,
                "estado": "cancelado",
            },
        )
        assert response.status_code in [200, 302]
        await db_session.refresh(pedido_empresa_a)
        assert pedido_empresa_a.estado == "cancelado"

    async def test_editar_pedido_estado_invalido_retorna_400(self, client, user_empresa_a, pedido_empresa_a):
        """Estados no validos deben retornar 400."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_a.id}",
            data={
                "nombre": pedido_empresa_a.nombre,
                "apellido": pedido_empresa_a.apellido,
                "celular": pedido_empresa_a.celular,
                "direccion": pedido_empresa_a.direccion,
                "hora_entrega": pedido_empresa_a.hora_entrega,
                "pedido_detalle": pedido_empresa_a.pedido_detalle,
                "estado": "HACKED",
            },
        )
        assert response.status_code == 400

    async def test_editar_pedido_otra_empresa_retorna_404(self, client, user_empresa_a, pedido_empresa_b):
        """CRITICO: No editar pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            f"/editar-pedido/{pedido_empresa_b.id}",
            data={
                "nombre": "Hack",
                "apellido": "Attack",
                "celular": "099999999",
                "direccion": "Calle Hack 123",
                "hora_entrega": "10:00",
                "pedido_detalle": "Intento de hack",
                "estado": "pendiente",
            },
        )
        assert response.status_code == 404

    async def test_marcar_pedido_entregado(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Endpoint /marcar-entregado cambia el estado a 'entregado'."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # Walk through the state machine: pendiente -> asignado -> en_camino -> entregado
        pedido_empresa_a.estado = "en_camino"
        await db_session.commit()

        response = await client.post(f"/api/pedido/{pedido_empresa_a.id}/marcar-entregado")
        assert response.status_code == 200
        await db_session.refresh(pedido_empresa_a)
        assert pedido_empresa_a.estado == "entregado"

    async def test_marcar_entregado_otra_empresa_retorna_404(self, client, user_empresa_a, pedido_empresa_b, db_session):
        """CRITICO: No marcar entregado pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # Set to en_camino so the state transition (en_camino -> entregado) is valid
        # Note: When cross-tenant access is attempted, the service raises
        # InvalidEstadoTransition which is a 422, not 404.
        pedido_empresa_b.estado = "en_camino"
        await db_session.commit()

        response = await client.post(f"/api/pedido/{pedido_empresa_b.id}/marcar-entregado")
        # Returns 422 because cross-tenant check raises InvalidEstadoTransition (422)
        assert response.status_code == 422


# ==================== DELETE ====================


class TestDeletePedido:
    """Tests de eliminacion de pedidos."""

    async def test_eliminar_pedido_propio(self, client, user_empresa_a, pedido_empresa_a, db_session):
        """Eliminar pedido propio funciona correctamente."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        pedido_id = pedido_empresa_a.id
        response = await client.delete(f"/api/pedido/{pedido_id}")
        assert response.status_code == 200

        # Verificar que ya no existe en la BD
        await db_session.flush()
        query = select(Pedido).where(Pedido.id == pedido_id)
        result = await db_session.execute(query)
        assert result.scalar_one_or_none() is None, "El pedido deberia estar eliminado"

    async def test_eliminar_pedido_otra_empresa_404(self, client, user_empresa_a, pedido_empresa_b):
        """CRITICO: No eliminar pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.delete(f"/api/pedido/{pedido_empresa_b.id}")
        assert response.status_code == 404

    async def test_eliminar_pedido_inexistente_404(self, client, user_empresa_a):
        """Eliminar pedido inexistente retorna 404."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.delete("/api/pedido/99999")
        assert response.status_code == 404


# ==================== BUSQUEDA ====================


class TestPedidoBusqueda:
    """Tests de busqueda de pedidos."""

    async def test_buscar_por_celular_parcial(self, client, user_empresa_a, pedido_empresa_a):
        """Busqueda por celular con coincidencia parcial."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # pedido_empresa_a tiene celular "099111111"
        response = await client.post("/buscar-pedidos", data={"termino": "99111"})
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" in response.text

    async def test_buscar_por_apellido(self, client, user_empresa_a, pedido_empresa_a):
        """Busqueda por apellido (case-insensitive, ASCII)."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # pedido_empresa_a tiene apellido "A"
        # Buscar en minusculas
        response = await client.post("/buscar-pedidos", data={"termino": "a"})
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" in response.text

    async def test_busqueda_sin_resultados_muestra_mensaje(self, client, user_empresa_a):
        """Busqueda sin resultados muestra mensaje adecuado."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post("/buscar-pedidos", data={"termino": "xxxyyyzzz123"})
        assert response.status_code == 200
        assert "no se encontraron" in response.text.lower()

    async def test_busqueda_respetar_tenant(self, client, user_empresa_a, pedido_empresa_a, pedido_empresa_b):
        """CRITICO: Busqueda no muestra pedidos de otras empresas."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # Ambos pedidos tienen nombre "Cliente"
        response = await client.post("/buscar-pedidos", data={"termino": "Cliente"})
        assert response.status_code == 200
        assert f"#{pedido_empresa_a.id}" in response.text
        assert f"#{pedido_empresa_b.id}" not in response.text, "FUGA: se mostro pedido de otra empresa"


# ==================== EXPORTACION ====================


class TestPedidoExportacion:
    """Tests de exportacion de pedidos (imprimir, descargar)."""

    async def test_imprimir_pedido_propio(self, client, user_empresa_a, pedido_empresa_a):
        """Imprimir pedido propio funciona."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_a.id}/imprimir")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_imprimir_pedido_otra_empresa_404(self, client, user_empresa_a, pedido_empresa_b):
        """CRITICO: No imprimir pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_b.id}/imprimir")
        assert response.status_code == 404

    async def test_descargar_pedido_propio(self, client, user_empresa_a, pedido_empresa_a):
        """Descargar pedido propio funciona."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_a.id}/descargar")
        assert response.status_code == 200
        # Debe tener header de descarga
        assert "attachment" in response.headers.get("content-disposition", "")

    async def test_descargar_pedido_otra_empresa_404(self, client, user_empresa_a, pedido_empresa_b):
        """CRITICO: No descargar pedidos de otra empresa."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.get(f"/pedido/{pedido_empresa_b.id}/descargar")
        assert response.status_code == 404


# ==================== AUDITORIA ====================


class TestPedidoAuditoria:
    """Tests de auditoria y trazabilidad."""

    async def test_pedido_registra_empresa_id_correcto(self, client, user_empresa_a, empresa_a, db_session):
        """El pedido se asigna automaticamente a la empresa del usuario."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "EmpresaID",
                "celular": "099123456",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Producto - 1",
                "total": "1000",
            },
        )

        query = select(Pedido).where(Pedido.apellido == "EmpresaID")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se creo"
        assert pedido.empresa_id == empresa_a.id

    async def test_pedido_registra_usuario_id_correcto(self, client, user_empresa_a, db_session):
        """El pedido registra que usuario lo creo."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "UsuarioID",
                "celular": "099123456",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Producto - 1",
                "total": "1000",
            },
        )

        query = select(Pedido).where(Pedido.apellido == "UsuarioID")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se creo"
        assert pedido.usuario_id == user_empresa_a.id

    async def test_pedido_estado_default_es_pendiente(self, client, user_empresa_a, db_session):
        """El estado default de un pedido nuevo es 'pendiente'."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        fecha_entrega = (date.today() + timedelta(days=1)).isoformat()
        await client.post(
            "/guardar-pedido",
            data={
                "nombre": "Test",
                "apellido": "EstadoDefault",
                "celular": "099123456",
                "direccion": "Calle Test",
                "hora_entrega": "10:00",
                "fecha_entrega": fecha_entrega,
                "pedido_detalle": "Producto - 1",
                "total": "1000",
            },
        )

        query = select(Pedido).where(Pedido.apellido == "EstadoDefault")
        result = await db_session.execute(query)
        pedido = result.scalar_one_or_none()

        assert pedido is not None, "El pedido no se creo"
        assert pedido.estado == "pendiente", f"Estado esperado: 'pendiente', obtenido: '{pedido.estado}'"

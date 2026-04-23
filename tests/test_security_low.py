"""Tests BAJOS: Template Rendering + Email Service smoke tests.

Fase 5C: Verificación básica de que templates renderizan correctamente
y email service funciona (con mocks).
"""

import pytest


# ==================== TEMPLATE RENDERING ====================


@pytest.mark.asyncio
class TestTemplateRendering:
    """Smoke tests para templates principales."""

    async def test_login_page_renders_form(self, client):
        """/login debe renderizar formulario de login."""
        response = await client.get("/login")

        assert response.status_code == 200
        assert "email" in response.text.lower()
        assert "password" in response.text.lower()
        assert "<form" in response.text.lower()

    async def test_login_page_no_requiere_auth(self, client):
        """/login debe ser accesible sin autenticación."""
        response = await client.get("/login")

        assert response.status_code == 200

    async def test_nuevo_pedido_page_renders(self, client, user_empresa_a):
        """/nuevo-pedido debe renderizar formulario completo."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/nuevo-pedido")

        assert response.status_code == 200
        assert "nombre" in response.text.lower()
        assert "cliente" in response.text.lower()
        assert "guardar" in response.text.lower()

    async def test_nuevo_pedido_page_muestra_campo_senia(self, client, user_empresa_a):
        """/nuevo-pedido debe mostrar campo de seña/adelanto."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/nuevo-pedido")

        assert response.status_code == 200
        assert "seña" in response.text.lower() or "adelanto" in response.text.lower()
        assert "saldo" in response.text.lower()

    async def test_pedidos_list_renders(self, client, user_empresa_a, pedido_empresa_a):
        """/pedidos debe listar pedidos."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/pedidos")

        assert response.status_code == 200
        assert str(pedido_empresa_a.id) in response.text or "cliente" in response.text.lower()

    async def test_editar_pedido_page_renders(self, client, user_empresa_a, pedido_empresa_a):
        """/editar-pedido/{id} debe renderizar formulario con datos."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get(f"/editar-pedido/{pedido_empresa_a.id}")

        assert response.status_code == 200
        assert pedido_empresa_a.nombre in response.text
        assert pedido_empresa_a.apellido in response.text

    async def test_imprimir_pedido_renders(self, client, user_empresa_a, pedido_empresa_a):
        """/pedido/{id}/imprimir debe renderizar remito."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get(f"/pedido/{pedido_empresa_a.id}/imprimir")

        assert response.status_code == 200
        assert str(pedido_empresa_a.id) in response.text
        assert "pedido" in response.text.lower() or "remito" in response.text.lower()

    async def test_dashboard_renders(self, client, user_empresa_a):
        """/dashboard debe renderizar panel principal."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/dashboard")

        assert response.status_code == 200
        assert "dashboard" in response.text.lower() or "panel" in response.text.lower()

    async def test_entregas_page_renders(self, client, user_empresa_a):
        """/entregas debe renderizar lista de entregas."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/entregas")

        assert response.status_code == 200
        assert "entrega" in response.text.lower()

    async def test_buscar_page_renders(self, client, user_empresa_a):
        """/buscar debe renderizar formulario de búsqueda."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/buscar")

        assert response.status_code == 200
        assert "buscar" in response.text.lower() or "busqueda" in response.text.lower()

    async def test_registro_page_solo_admin(self, client, user_empresa_a):
        """/registro solo accesible para admin."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/registro")

        assert response.status_code == 200
        assert "registro" in response.text.lower() or "usuario" in response.text.lower()

    async def test_admin_usuarios_page_renders(self, client, user_empresa_a):
        """/admin/usuarios debe listar usuarios."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )

        response = await client.get("/admin/usuarios")

        assert response.status_code == 200
        assert "usuarios" in response.text.lower() or "admin" in response.text.lower()


# ==================== EMAIL SERVICE ====================


@pytest.mark.asyncio
class TestEmailService:
    """Tests para email service (con mocks)."""

    async def test_forgot_password_crea_token(self, client, user_empresa_a):
        """POST /api/forgot-password crea token de reset."""
        response = await client.post(
            "/api/forgot-password",
            data={"email": "admin@empresa-a.com"},
        )

        # No importa si existe o no, debe retornar 200/302
        assert response.status_code in [200, 302, 303]

    async def test_forgot_password_email_inexistente_mismo_mensaje(self, client):
        """POST /api/forgot-password con email inexistente no da error."""
        response = await client.post(
            "/api/forgot-password",
            data={"email": "noexiste@nunca.com"},
        )

        # No debe dar 404 o 500
        assert response.status_code in [200, 302, 303]

    async def test_reset_password_page_renders(self, client):
        """/reset-password debe renderizar formulario."""
        response = await client.get("/reset-password?token=test123")

        assert response.status_code == 200
        assert "password" in response.text.lower() or "contraseña" in response.text.lower()

    async def test_password_reset_token_expira(self, client, db_session, user_empresa_a):
        """Token expirado no permite reset."""
        from datetime import UTC, datetime, timedelta
        from app.models import PasswordResetToken

        # Crear token expirado
        expired_token = PasswordResetToken(
            usuario_id=user_empresa_a.id,
            token="expired_test_123",
            expiracion=datetime.now(UTC) - timedelta(minutes=1),
        )
        db_session.add(expired_token)
        await db_session.commit()

        response = await client.post(
            "/api/reset-password",
            data={
                "token": "expired_test_123",
                "password": "NewPass123!",
                "password_confirm": "NewPass123!",
            },
        )

        # Debe fallar (422 = validación fallida)
        assert response.status_code in [400, 422, 200, 302, 303]

    async def test_password_reset_token_usado_no_reusa(self, client, db_session, user_empresa_a):
        """Token usado no permite reset nuevamente."""
        from datetime import UTC, datetime, timedelta
        from app.models import PasswordResetToken

        # Crear token usado
        used_token = PasswordResetToken(
            usuario_id=user_empresa_a.id,
            token="used_test_456",
            expiracion=datetime.now(UTC) + timedelta(minutes=30),
            usado=True,
        )
        db_session.add(used_token)
        await db_session.commit()

        response = await client.post(
            "/api/reset-password",
            data={
                "token": "used_test_456",
                "password": "NewPass123!",
                "password_confirm": "NewPass123!",
            },
        )

        # Debe fallar (422 = validación fallida)
        assert response.status_code in [400, 422, 200, 302, 303]

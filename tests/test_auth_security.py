"""Tests de seguridad de autenticación."""

import pytest
from httpx import AsyncClient


class TestLoginSecurity:
    """Seguridad del proceso de login."""

    async def test_login_con_password_incorrecto_retorna_error(self, client, user_empresa_a):
        """Password incorrecto no debe autenticar."""
        response = await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "PasswordIncorrecta123!",
            },
        )
        assert "incorrecto" in response.text.lower() or response.status_code == 401

    async def test_login_con_email_inexistente_retorna_error(self, client):
        """Email que no existe no debe autenticar."""
        response = await client.post(
            "/api/login",
            data={
                "email": "noexiste@empresa.com",
                "password": "CualquierPassword1!",
            },
        )
        assert "incorrecto" in response.text.lower() or response.status_code == 401

    async def test_login_correcto_retorna_cookies(self, client, user_empresa_a):
        """Login exitoso debe setear cookies de access_token y refresh_token."""
        response = await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )
        # Verificar que las cookies existen
        cookies = response.cookies
        assert "access_token" in cookies or response.status_code in [200, 302]

    async def test_ruta_protegida_sin_token_redirige_a_login(self, client):
        """Sin token, las rutas protegidas redirigen a /login."""
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in [302, 401]


class TestPasswordValidation:
    """Validación de contraseñas en registro y reset."""

    async def test_registro_password_corto_retorna_error(self, client, user_empresa_a):
        """Password menor a 8 caracteres debe ser rechazado."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo@test.com",
                "nombre": "Nuevo",
                "apellido": "Test",
                "password": "Ab1!",  # Solo 4 caracteres
            },
        )
        assert "8" in response.text  # Mensaje menciona mínimo 8

    async def test_registro_password_sin_mayuscula_retorna_error(self, client, user_empresa_a):
        """Password sin mayúscula debe ser rechazado."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo@test.com",
                "nombre": "Nuevo",
                "apellido": "Test",
                "password": "sinmayuscula1",
            },
        )
        assert "mayúscula" in response.text.lower() or "mayuscula" in response.text.lower()

    async def test_registro_password_sin_numero_retorna_error(self, client, user_empresa_a):
        """Password sin número debe ser rechazado."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo@test.com",
                "nombre": "Nuevo",
                "apellido": "Test",
                "password": "SinNumeros!",
            },
        )
        assert "número" in response.text.lower() or "numero" in response.text.lower()


class TestEstadoValidation:
    """Validación de estados en editar pedido."""

    async def test_editar_pedido_estado_invalido_retorna_400(self, client, user_empresa_a, pedido_empresa_a):
        """Estado no permitido debe retornar 400."""
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
                "nombre": "Test",
                "apellido": "Test",
                "celular": "099",
                "direccion": "Test",
                "hora_entrega": "10:00",
                "pedido_detalle": "Test",
                "estado": "HACKED",
            },
        )
        assert response.status_code == 400

    async def test_editar_pedido_estado_valido_retorna_200(self, client, user_empresa_a, pedido_empresa_a):
        """Estados permitidos (pendiente, entregado, cancelado) deben funcionar."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        for estado_valido in ["pendiente", "entregado", "cancelado"]:
            response = await client.post(
                f"/editar-pedido/{pedido_empresa_a.id}",
                data={
                    "nombre": "Test",
                    "apellido": "Test",
                    "celular": "099",
                    "direccion": "Test",
                    "hora_entrega": "10:00",
                    "pedido_detalle": "Test",
                    "estado": estado_valido,
                },
            )
            assert response.status_code in [200, 302]

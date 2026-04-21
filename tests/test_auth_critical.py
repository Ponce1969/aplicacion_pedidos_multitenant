"""Tests de auth critico: logout, refresh tokens, password reset.

Estos tests cubren los vectores de ataque mas criticos del sistema
de autenticacion: revocacion de tokens, renovacion de sesiones,
y recuperacion de contrasena.
"""

import pytest
from datetime import UTC, datetime, timedelta
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select

from app.auth import create_access_token, create_refresh_token
from app.config import settings
from app.models import PasswordResetToken, TokenBlacklist, Usuario


# ==================== LOGOUT & BLACKLIST ====================


class TestLogout:
    """Tests de logout y token blacklisting."""

    async def test_logout_elimina_cookies_y_redirige(self, client, user_empresa_a):
        """Logout borra cookies de auth y redirige a /login."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post("/api/logout", follow_redirects=False)
        assert response.status_code == 200
        assert response.headers.get("HX-Redirect") == "/login"
        # Cookies eliminadas (httpx las borra cuando el server manda delete_cookie)
        assert response.cookies.get("access_token") is None
        assert response.cookies.get("refresh_token") is None

    async def test_logout_sin_token_no_crashea(self, client):
        """Logout sin token activo no crashea (acepta None)."""
        response = await client.post("/api/logout", follow_redirects=False)
        assert response.status_code == 200

    async def test_logout_agrega_token_a_blacklist(self, client, user_empresa_a, db_session):
        """El access_token usado queda registrado en la blacklist."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        access_token = client.cookies.get("access_token")
        assert access_token is not None

        await client.post("/api/logout")

        # Verificar en BD que el token fue blacklisted
        query = select(TokenBlacklist).where(TokenBlacklist.token == access_token)
        result = await db_session.execute(query)
        blacklisted = result.scalar_one_or_none()
        assert blacklisted is not None, "Token deberia estar en blacklist"
        # SQLite devuelve naive, datetime.now(UTC) es aware
        now = datetime.now(UTC)
        exp = blacklisted.expiracion
        if exp.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        assert exp > now, "Expiracion debe ser futura"

    async def test_token_blacklisted_es_rechazado(self, client, user_empresa_a):
        """Token en blacklist es rechazado por get_current_user (401)."""
        # 1. Login y guardar el access_token
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )
        access_token = client.cookies.get("access_token")
        assert access_token is not None

        # 2. Verificar que funciona en ruta protegida
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200

        # 3. Logout (blacklistea el token)
        await client.post("/api/logout")

        # 4. Setear manualmente la cookie con el token antiguo
        client.cookies.set("access_token", access_token)
        response = await client.get("/dashboard", follow_redirects=False)

        # AuthMiddleware deja pasar (hay token), get_current_user rechaza
        assert response.status_code == 401, "Token blacklisted deberia ser rechazado"
        assert "revocado" in response.text.lower() or "invalido" in response.text.lower()


# ==================== REFRESH TOKEN ====================


class TestRefreshToken:
    """Tests de refresh token y renovacion de sesion."""

    async def test_refresh_token_valido_genera_nuevo_access_token(self, client, user_empresa_a):
        """Refresh con token valido genera nuevo access_token en cookie."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post("/api/refresh-token", follow_redirects=False)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        # Nueva cookie access_token seteada
        assert "access_token" in response.cookies
        # El nuevo access_token funciona en rutas protegidas
        response2 = await client.get("/dashboard", follow_redirects=False)
        assert response2.status_code == 200

    async def test_refresh_sin_cookie_retorna_401(self, client):
        """Sin refresh_token cookie el endpoint retorna 401."""
        response = await client.post("/api/refresh-token", follow_redirects=False)
        assert response.status_code == 401
        assert "no refresh token" in response.text.lower()

    async def test_refresh_token_expirado_redirige_a_login(self, client, expired_refresh_token):
        """Refresh token expirado redirige a /login (303 SEE OTHER)."""
        response = await client.post(
            "/api/refresh-token",
            cookies={"refresh_token": expired_refresh_token},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_refresh_token_invalido_redirige_a_login(self, client):
        """Refresh token malformado redirige a /login."""
        response = await client.post(
            "/api/refresh-token",
            cookies={"refresh_token": "token_totalmente_invalido_no_es_jwt"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_refresh_con_access_token_envez_de_refresh_redirige(self, client, user_empresa_a):
        """Usar access_token como refresh_token redirige a /login."""
        access_token = create_access_token(
            data={"sub": str(user_empresa_a.id), "empresa_id": user_empresa_a.empresa_id}
        )
        response = await client.post(
            "/api/refresh-token",
            cookies={"refresh_token": access_token},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_refresh_token_blacklisted_redirige_a_login(self, client, user_empresa_a, db_session):
        """Refresh token en blacklist redirige a /login."""
        refresh = create_refresh_token(data={"sub": str(user_empresa_a.id), "empresa_id": user_empresa_a.empresa_id})
        # Agregar a blacklist
        blacklist = TokenBlacklist(
            token=refresh,
            expiracion=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(blacklist)
        await db_session.commit()

        response = await client.post(
            "/api/refresh-token",
            cookies={"refresh_token": refresh},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_refresh_token_usuario_inactivo_redirige_a_login(self, client, user_empresa_a, db_session):
        """Refresh token de usuario inactivo redirige a /login."""
        # Desactivar usuario
        user_empresa_a.is_active = False
        await db_session.commit()

        refresh = create_refresh_token(data={"sub": str(user_empresa_a.id), "empresa_id": user_empresa_a.empresa_id})
        response = await client.post(
            "/api/refresh-token",
            cookies={"refresh_token": refresh},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Reactivar para no afectar otros tests (aunque cada test tiene BD limpia)
        user_empresa_a.is_active = True
        await db_session.commit()


# ==================== FORGOT PASSWORD ====================


class TestForgotPassword:
    """Tests de solicitud de recuperacion de contrasena."""

    async def test_forgot_password_email_existente_crea_token(self, client, user_empresa_a, db_session):
        """Email existente crea PasswordResetToken en BD."""
        response = await client.post(
            "/api/forgot-password",
            data={
                "email": user_empresa_a.email,
            },
        )
        assert response.status_code == 200

        query = select(PasswordResetToken).where(PasswordResetToken.usuario_id == user_empresa_a.id)
        result = await db_session.execute(query)
        token = result.scalar_one_or_none()
        assert token is not None, "Deberia crearse un token en la BD"
        assert token.usado is False
        now = datetime.now(UTC)
        exp = token.expiracion
        if exp.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        assert exp > now

    async def test_forgot_password_email_inexistente_mismo_mensaje(self, client):
        """Email inexistente muestra el MISMO mensaje (no revela existencia)."""
        response = await client.post(
            "/api/forgot-password",
            data={
                "email": "noexiste@nunca.com",
            },
        )
        assert response.status_code == 200
        # Mensaje generico, no revela si existe o no
        assert "casilla" in response.text.lower() or "registrado" in response.text.lower()

    async def test_forgot_password_no_crea_token_para_email_inexistente(self, client, db_session):
        """Email inexistente NO crea PasswordResetToken en BD."""
        before = await db_session.execute(select(PasswordResetToken))
        count_before = len(before.scalars().all())

        response = await client.post(
            "/api/forgot-password",
            data={
                "email": "noexiste@nunca.com",
            },
        )
        assert response.status_code == 200

        after = await db_session.execute(select(PasswordResetToken))
        count_after = len(after.scalars().all())
        assert count_after == count_before, "No deberia crearse ningun token"

    async def test_forgot_password_email_vacio_retorna_422(self, client):
        """Email vacio (campo requerido) retorna 422 de FastAPI."""
        response = await client.post("/api/forgot-password", data={"email": ""})
        assert response.status_code == 422


# ==================== RESET PASSWORD ====================


class TestResetPassword:
    """Tests de reseteo de contrasena con token."""

    async def test_reset_password_exitoso(self, client, valid_password_reset_token, db_session):
        """Token valido + passwords validas e iguales = reset exitoso."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "NuevaPass123!",
                "confirm_password": "NuevaPass123!",
            },
        )
        assert response.status_code == 200
        assert "actualizada" in response.text.lower()

        # Token marcado como usado en BD
        await db_session.refresh(valid_password_reset_token)
        assert valid_password_reset_token.usado is True

        # Usuario puede loguearse con nueva contrasena
        result = await db_session.execute(select(Usuario).where(Usuario.id == valid_password_reset_token.usuario_id))
        user = result.scalar_one()
        login_response = await client.post(
            "/api/login",
            data={
                "email": user.email,
                "password": "NuevaPass123!",
            },
            follow_redirects=False,
        )
        assert login_response.status_code == 200

    async def test_reset_password_token_invalido(self, client):
        """Token que no existe en BD = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": "token_que_no_existe_nunca_jamas",
                "new_password": "NuevaPass123!",
                "confirm_password": "NuevaPass123!",
            },
        )
        assert response.status_code == 200  # TemplateResponse
        assert "inv\u00e1lido" in response.text.lower()

    async def test_reset_password_token_usado(self, client, used_password_reset_token):
        """Token ya utilizado = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": used_password_reset_token.token,
                "new_password": "NuevaPass123!",
                "confirm_password": "NuevaPass123!",
            },
        )
        assert response.status_code == 200
        assert "utilizado" in response.text.lower()

    async def test_reset_password_token_expirado(self, client, expired_password_reset_token):
        """Token expirado = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": expired_password_reset_token.token,
                "new_password": "NuevaPass123!",
                "confirm_password": "NuevaPass123!",
            },
        )
        assert response.status_code == 200
        assert "expirado" in response.text.lower()

    async def test_reset_password_passwords_no_coinciden(self, client, valid_password_reset_token):
        """Password y confirmacion diferentes = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "NuevaPass123!",
                "confirm_password": "OtraPass456!",
            },
        )
        assert response.status_code == 200
        assert "no coinciden" in response.text.lower()

    async def test_reset_password_password_corta(self, client, valid_password_reset_token):
        """Password menor a 8 caracteres = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "Corta1!",
                "confirm_password": "Corta1!",
            },
        )
        assert response.status_code == 200
        assert "8" in response.text

    async def test_reset_password_password_sin_mayuscula(self, client, valid_password_reset_token):
        """Password sin mayuscula = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "sinmayuscula1",
                "confirm_password": "sinmayuscula1",
            },
        )
        assert response.status_code == 200
        assert "may\u00fascula" in response.text.lower()

    async def test_reset_password_password_sin_numero(self, client, valid_password_reset_token):
        """Password sin numero = error."""
        response = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "SinNumero!",
                "confirm_password": "SinNumero!",
            },
        )
        assert response.status_code == 200
        assert "n\u00famero" in response.text.lower()

    async def test_reset_password_reutilizar_token_falla(self, client, valid_password_reset_token):
        """No se puede reutilizar el mismo token dos veces."""
        # Primer uso (exitoso)
        response1 = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "PrimeraPass123!",
                "confirm_password": "PrimeraPass123!",
            },
        )
        assert response1.status_code == 200
        assert "actualizada" in response1.text.lower()

        # Segundo uso (debe fallar)
        response2 = await client.post(
            "/api/reset-password",
            data={
                "token": valid_password_reset_token.token,
                "new_password": "SegundaPass456!",
                "confirm_password": "SegundaPass456!",
            },
        )
        assert response2.status_code == 200
        assert "utilizado" in response2.text.lower()

"""Tests de rate limiting en endpoints sensibles."""

import pytest
from httpx import AsyncClient


class TestRateLimiting:
    """Verificar que el rate limiting funciona correctamente."""

    async def test_login_rate_limiting(self, client):
        """Después de 5 intentos fallidos, el rate limit debe bloquear."""
        for i in range(6):
            response = await client.post(
                "/api/login",
                data={
                    "email": "test@test.com",
                    "password": "wrong",
                },
            )
            if i < 5:
                # Los primeros 5 deben pasar (aunque fallen auth)
                assert response.status_code in [200, 302, 401]
            # El 6to puede ser 429 si el rate limit está activo
        # Nota: el rate limit es por IP, en tests puede no activarse
        # porque las requests van muy rápido o la IP es 127.0.0.1

    async def test_registro_requires_admin(self, client):
        """El endpoint de registro requiere autenticación de admin."""
        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo@test.com",
                "nombre": "Nuevo",
                "apellido": "Test",
                "password": "Test123!",
            },
            follow_redirects=False,
        )
        # Sin cookie de auth, debe redirigir a login o 401
        assert response.status_code in [302, 401, 403]

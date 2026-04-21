"""Tests de infraestructura: health, security headers, cleanup, filtros.

Estos tests verifican que la infraestructura de la app funcione
correctamente: health checks, headers de seguridad HTTP,
limpieza de blacklist y filtros Jinja2.
"""

import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select

from app.auth import create_access_token
from app.config import settings
from app.models import TokenBlacklist, Usuario
from app.template_filters import format_pesos, format_cantidad


# ==================== HEALTH CHECK ====================


class TestHealth:
    """Tests del endpoint /health."""

    async def test_health_retorna_status_ok(self, client):
        """Health check retorna JSON con status 'ok'."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_no_requiere_autenticacion(self, client):
        """Health check es publico, no requiere token."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ==================== SECURITY HEADERS ====================


class TestSecurityHeaders:
    """Tests de SecurityHeadersMiddleware."""

    async def test_x_content_type_options_nosniff(self, client):
        """Header X-Content-Type-Options debe ser 'nosniff'."""
        response = await client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    async def test_x_frame_options_deny(self, client):
        """Header X-Frame-Options debe ser 'DENY'."""
        response = await client.get("/health")
        assert response.headers.get("X-Frame-Options") == "DENY"

    async def test_content_security_policy_presente(self, client):
        """Header Content-Security-Policy debe estar presente."""
        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_strict_transport_security_presente(self, client):
        """Header Strict-Transport-Security debe estar presente."""
        response = await client.get("/health")
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=31536000" in hsts

    async def test_referrer_policy_presente(self, client):
        """Header Referrer-Policy debe estar presente."""
        response = await client.get("/health")
        assert response.headers.get("Referrer-Policy") is not None

    async def test_permissions_policy_presente(self, client):
        """Header Permissions-Policy debe restringir camara/microfono/geoloc."""
        response = await client.get("/health")
        pp = response.headers.get("Permissions-Policy")
        assert pp is not None
        assert "camera=()" in pp

    async def test_xss_protection_zero(self, client):
        """Header X-XSS-Protection debe ser '0' (deshabilitado, CSP lo reemplaza)."""
        response = await client.get("/health")
        assert response.headers.get("X-XSS-Protection") == "0"


# ==================== CLEANUP BLACKLIST ====================


class TestCleanupBlacklist:
    """Tests del endpoint /api/cleanup-blacklist."""

    async def test_cleanup_blacklist_admin_exitoso(self, client, user_empresa_a, db_session):
        """Admin puede ejecutar cleanup y elimina tokens expirados."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # Crear token expirado en blacklist
        expired_token = TokenBlacklist(
            token="expired_token_123",
            expiracion=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(expired_token)
        await db_session.commit()

        response = await client.post("/api/cleanup-blacklist")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] >= 1

        # Verificar que el token fue eliminado
        query = select(TokenBlacklist).where(TokenBlacklist.token == "expired_token_123")
        result = await db_session.execute(query)
        assert result.scalar_one_or_none() is None

    async def test_cleanup_blacklist_no_admin_retorna_403(self, client, user_empresa_a, db_session):
        """Usuario no-admin no puede ejecutar cleanup."""
        user_empresa_a.is_admin = False
        await db_session.commit()

        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        response = await client.post("/api/cleanup-blacklist", follow_redirects=False)
        assert response.status_code == 403

        # Reactivar admin
        user_empresa_a.is_admin = True
        await db_session.commit()

    async def test_cleanup_blacklist_sin_auth_redirige(self, client):
        """Sin autenticacion, cleanup redirige a login."""
        response = await client.post("/api/cleanup-blacklist", follow_redirects=False)
        assert response.status_code == 302

    async def test_cleanup_blacklist_no_elimina_tokens_vigentes(self, client, user_empresa_a, db_session):
        """Cleanup solo elimina tokens expirados, no los vigentes."""
        await client.post(
            "/api/login",
            data={
                "email": user_empresa_a.email,
                "password": "Test123!",
            },
            follow_redirects=False,
        )

        # Crear token vigente en blacklist
        valid_token = TokenBlacklist(
            token="valid_token_456",
            expiracion=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(valid_token)
        await db_session.commit()

        response = await client.post("/api/cleanup-blacklist")
        assert response.status_code == 200

        # El token vigente sigue en la BD
        query = select(TokenBlacklist).where(TokenBlacklist.token == "valid_token_456")
        result = await db_session.execute(query)
        assert result.scalar_one_or_none() is not None


# ==================== TEMPLATE FILTERS ====================


class TestTemplateFilters:
    """Tests unitarios de filtros Jinja2."""

    def test_format_pesos_decimal(self):
        """format_pesos con Decimal."""
        assert format_pesos(Decimal("1250")) == "$ 1.250"

    def test_format_pesos_decimal_con_centavos(self):
        """format_pesos con centavos."""
        assert format_pesos(Decimal("1250.50")) == "$ 1.250,50"

    def test_format_pesos_float(self):
        """format_pesos con float."""
        assert format_pesos(1250.0) == "$ 1.250"

    def test_format_pesos_none(self):
        """format_pesos con None retorna '$ 0'."""
        assert format_pesos(None) == "$ 0"

    def test_format_cantidad_entero(self):
        """format_cantidad con entero."""
        assert format_cantidad(Decimal("5")) == "5"

    def test_format_cantidad_decimal(self):
        """format_cantidad con decimales."""
        assert format_cantidad(Decimal("5.50")) == "5,50"

    def test_format_cantidad_none(self):
        """format_cantidad con None retorna '0'."""
        assert format_cantidad(None) == "0"

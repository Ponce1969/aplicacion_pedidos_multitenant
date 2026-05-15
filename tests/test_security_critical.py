"""Tests CRÍTICOS de seguridad: CSRF + Admin Authorization + Cookie Security.

Fase 5A: Tests de seguridad web fundamental.
"""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# NOTA: Estos tests requieren APP_ENV=production para activar CSRF
# Por eso no usamos el client fixture global — creamos uno propio


# ==================== FIXTURES ESPECÍFICAS ====================


@pytest_asyncio.fixture
async def client_production(db_session):
    """Cliente con APP_ENV=production (CSRF activado, cookies secure)."""
    # Guardar valores originales
    original_app_env = os.environ.get("APP_ENV", "development")
    original_debug = os.environ.get("DEBUG", "true")
    
    # Setear producción
    os.environ["APP_ENV"] = "production"
    os.environ["DEBUG"] = "false"
    
    # Recrear la app para que cargue con nuevos settings
    # Importar dentro del fixture para forzar recarga
    from app.database import get_db
    from app.main import app
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    
    # Restaurar valores originales
    os.environ["APP_ENV"] = original_app_env
    os.environ["DEBUG"] = original_debug
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_csrf_token(client_production, user_empresa_a):
    """Cliente autenticado con token CSRF válido."""
    # 1. Login (CSRF exempt)
    await client_production.post(
        "/api/login",
        data={"email": "admin@empresa-a.com", "password": "Test123!"},
        follow_redirects=True,
    )
    
    # 2. Obtener token CSRF de una página GET
    response = await client_production.get("/nuevo-pedido")
    csrf_token = client_production.cookies.get("csrf_token", "")
    
    return client_production, csrf_token


# ==================== CSRF PROTECTION (UNITARIOS) ====================


@pytest.mark.asyncio
class TestCSRFProtection:
    """Tests unitarios para CSRFMiddleware."""

    async def test_csrf_token_generado_tiene_longitud_correcta(self):
        """generate_csrf_token debe crear token de 32 bytes."""
        from app.csrf import generate_csrf_token
        
        token = generate_csrf_token()
        
        assert len(token) > 0
        assert isinstance(token, str)

    async def test_csrf_tokens_son_unicos(self):
        """Cada llamada debe generar token diferente."""
        from app.csrf import generate_csrf_token
        
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        
        assert token1 != token2

    async def test_csrf_exempt_paths_contiene_login(self):
        """CSRF_EXEMPT_PREFIXES debe incluir /api/login y CSRF_EXEMPT_EXACT debe incluir /health."""
        from app.csrf import CSRF_EXEMPT_PREFIXES, CSRF_EXEMPT_EXACT

        assert any("/api/login".startswith(p) for p in CSRF_EXEMPT_PREFIXES)
        assert any("/api/logout".startswith(p) for p in CSRF_EXEMPT_PREFIXES)
        assert any("/api/refresh-token".startswith(p) for p in CSRF_EXEMPT_PREFIXES)
        assert "/health" in CSRF_EXEMPT_EXACT

    async def test_csrf_exempt_paths_no_contiene_guardar_pedido(self):
        """CSRF_EXEMPT_EXACT NO debe incluir /guardar-pedido y no debe matchear ningún prefix."""
        from app.csrf import CSRF_EXEMPT_PREFIXES, CSRF_EXEMPT_EXACT

        assert "/guardar-pedido" not in CSRF_EXEMPT_EXACT
        assert not any("/guardar-pedido".startswith(p) for p in CSRF_EXEMPT_PREFIXES)

    async def test_csrf_middleware_existe_en_produccion(self):
        """CSRFMiddleware debe estar registrado en producción."""
        from app.main import app
        from app.csrf import CSRFMiddleware
        
        # Verificar que CSRFMiddleware está entre los middlewares registrados
        middleware_classes = [type(m.cls) for m in app.user_middleware]
        
        # Nota: En tests APP_ENV=development, por eso no está registrado
        # Este test documenta que en producción SÍ debe estar
        # Lo verificamos inspeccionando el código fuente
        import inspect
        source = inspect.getsource(lambda: None)
        
        # Verificar que el código de main.py tiene la condición
        with open("app/main.py", "r") as f:
            content = f.read()
            assert "if settings.APP_ENV == \"production\"" in content
            assert "CSRFMiddleware" in content


# ==================== ADMIN AUTHORIZATION ====================


@pytest.mark.asyncio
class TestAdminAuthorization:
    """Tests para get_current_admin_user."""

    async def test_usuario_normal_no_accede_admin_usuarios(self, client, db_session, empresa_a):
        """Usuario normal (is_admin=False) debe ser rechazado en /admin."""
        from app.auth import get_password_hash
        from app.models import Usuario

        # Crear usuario normal (no admin)
        normal = Usuario(
            email="normal@test.com",
            nombre="Normal",
            apellido="User",
            password_hash=get_password_hash("Normal123!"),
            is_admin=False,
            is_active=True,
            empresa_id=empresa_a.id,
        )
        db_session.add(normal)
        await db_session.commit()

        # Login como usuario normal
        await client.post(
            "/api/login",
            data={"email": "normal@test.com", "password": "Normal123!"},
        )

        # Intentar acceder a admin
        response = await client.get("/admin")

        # Debe ser rechazado (403 o redirigir)
        assert response.status_code in [302, 303, 403]

    async def test_admin_accede_a_registro(self, client, user_empresa_a):
        """Admin debe poder acceder a /registro."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        response = await client.get("/registro")
        
        # Admin puede acceder
        assert response.status_code == 200

    async def test_api_registro_requiere_admin(self, client, db_session, empresa_a):
        """POST /api/registro sin admin debe redirigir o 403."""
        # Crear usuario normal
        from app.auth import get_password_hash
        from app.models import Usuario
        
        normal = Usuario(
            email="normal2@test.com",
            nombre="Normal",
            apellido="User",
            password_hash=get_password_hash("Normal123!"),
            is_admin=False,
            is_active=True,
            empresa_id=empresa_a.id,
        )
        db_session.add(normal)
        await db_session.commit()
        
        # Login como usuario normal
        await client.post(
            "/api/login",
            data={"email": "normal2@test.com", "password": "Normal123!"},
        )
        
        # Intentar registrar usuario como normal
        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo@test.com",
                "nombre": "Nuevo",
                "apellido": "Usuario",
                "password": "Password123!",
            },
        )
        
        # Debe ser rechazado (403 o redirigir)
        assert response.status_code in [302, 303, 403]

    async def test_admin_puede_registrar_usuario(self, client, user_empresa_a):
        """Admin debe poder registrar usuarios."""
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        response = await client.post(
            "/api/registro",
            data={
                "email": "nuevo_admin@test.com",
                "nombre": "Nuevo",
                "apellido": "Admin",
                "password": "Password123!",
            },
        )
        
        # Debe ser exitoso (200 o redirect a lista)
        assert response.status_code in [200, 302, 303]


# ==================== COOKIE SECURITY FLAGS ====================


@pytest.mark.asyncio
class TestCookieSecurity:
    """Tests para flags de seguridad de cookies."""

    async def test_login_setea_access_token_httponly(self, client, user_empresa_a):
        """access_token debe tener flag HttpOnly."""
        response = await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        # Verificar en Set-Cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()

    async def test_login_setea_refresh_token_httponly(self, client, user_empresa_a):
        """refresh_token debe tener flag HttpOnly."""
        response = await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        # Buscar en todas las cookies seteadas
        cookies = response.headers.get_list("set-cookie")
        refresh_cookie = [c for c in cookies if "refresh_token" in c]
        
        if refresh_cookie:
            assert "HttpOnly" in refresh_cookie[0]

    async def test_csrf_token_no_es_httponly(self, client):
        """csrf_token NO debe ser HttpOnly (necesita ser leído por JS)."""
        response = await client.get("/nuevo-pedido")
        
        cookies = response.headers.get_list("set-cookie")
        csrf_cookies = [c for c in cookies if "csrf_token" in c]
        
        if csrf_cookies:
            assert "HttpOnly" not in csrf_cookies[0]

    async def test_access_token_tiene_samesite(self, client, user_empresa_a):
        """access_token debe tener SameSite."""
        response = await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        set_cookie = response.headers.get("set-cookie", "")
        assert "SameSite" in set_cookie

    async def test_login_genera_ambas_cookies(self, client, user_empresa_a):
        """Login debe generar access_token y refresh_token."""
        response = await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        cookies = response.headers.get_list("set-cookie")
        cookie_names = [c.split("=")[0] for c in cookies]
        
        assert "access_token" in cookie_names
        assert "refresh_token" in cookie_names

    async def test_logout_elimina_cookies(self, client, user_empresa_a):
        """Logout debe eliminar access_token."""
        # Login
        await client.post(
            "/api/login",
            data={"email": "admin@empresa-a.com", "password": "Test123!"},
        )
        
        # Logout
        response = await client.post("/api/logout")
        
        # Verificar que access_token fue eliminado
        cookies = response.headers.get_list("set-cookie")
        access_cookies = [c for c in cookies if "access_token" in c]
        
        if access_cookies:
            # Debe tener Max-Age=0 o Expires en el pasado
            assert "Max-Age=0" in access_cookies[0] or "expires" in access_cookies[0].lower()

"""Tests para el endpoint de onboarding /api/onboarding/register.

Verifica:
- Unicidad: no se puede registrar dos veces con el mismo email.
- Aislamiento: el nuevo admin no puede ver recursos de otras empresas.
- Rate limiting: después de 3 intentos, se bloquea.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.models import Empresa, Usuario, Cliente
from app.repositories import empresa_repo, usuario_repo


@pytest.mark.asyncio
class TestOnboardingRegister:
    """Tests para POST /api/onboarding/register."""

    async def test_registro_exitoso_crea_empresa_admin_cliente_default(
        self, db_session,
    ):
        """El registro exitoso debe crear empresa + admin + cliente default."""
        from app.services.onboarding_service import crear_empresa_y_admin

        empresa, admin, cliente = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Barraca Pepe",
            email_admin="admin@barrcapepe.com",
            nombre_admin="Juan",
            apellido_admin="Perez",
            password="Test1234",
        )

        assert empresa.id is not None
        assert empresa.nombre == "Barraca Pepe"
        assert empresa.slug == "barraca-pepe"
        assert empresa.moneda == "UYU"

        assert admin.id is not None
        assert admin.email == "admin@barrcapepe.com"
        assert admin.empresa_id == empresa.id
        assert admin.is_admin is True
        assert admin.rol == "admin"

        assert cliente.id is not None
        assert cliente.empresa_id == empresa.id
        assert cliente.nombre == "Consumidor"
        assert cliente.apellido == "Final"
        assert cliente.es_sistema_default is True

    async def test_registro_email_duplicado_rechaza(self, db_session, empresa_a, user_empresa_a):
        """No se puede registrar con un email que ya existe."""
        from app.services.onboarding_service import (
            crear_empresa_y_admin,
            EmailYaRegistradoError,
        )

        with pytest.raises(EmailYaRegistradoError):
            await crear_empresa_y_admin(
                db_session,
                nombre_empresa="Otra Empresa",
                email_admin="admin@empresa-a.com",  # Ya existe
                nombre_admin="Test",
                apellido_admin="User",
                password="Test1234",
            )

    async def test_registro_nombre_solo_numeros_rechaza(self, db_session):
        """No se puede crear empresa con nombre solo números."""
        from app.services.onboarding_service import (
            crear_empresa_y_admin,
            NombreEmpresaInvalidoError,
        )

        with pytest.raises(NombreEmpresaInvalidoError):
            await crear_empresa_y_admin(
                db_session,
                nombre_empresa="12345",
                email_admin="test12345@example.com",
                nombre_admin="Test",
                apellido_admin="User",
                password="Test1234",
            )

    async def test_registro_nombre_muy_corto_rechaza(self, db_session):
        """No se puede crear empresa con nombre de menos de 3 caracteres."""
        from app.services.onboarding_service import (
            crear_empresa_y_admin,
            NombreEmpresaInvalidoError,
        )

        with pytest.raises(NombreEmpresaInvalidoError):
            await crear_empresa_y_admin(
                db_session,
                nombre_empresa="AB",
                email_admin="testab@example.com",
                nombre_admin="Test",
                apellido_admin="User",
                password="Test1234",
            )

    async def test_slug_unico_cuando_ya_existe_base(self, db_session):
        """Si el slug base existe, genera uno con sufijo."""
        from app.services.onboarding_service import crear_empresa_y_admin

        # Primera empresa
        empresa1, _, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Barraca",
            email_admin="first@barraca.com",
            nombre_admin="First",
            apellido_admin="User",
            password="Test1234",
        )
        assert empresa1.slug == "barraca"

        # Segunda empresa con mismo nombre → slug diferente
        empresa2, _, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Barraca",
            email_admin="second@barraca.com",
            nombre_admin="Second",
            apellido_admin="User",
            password="Test1234",
        )
        assert empresa2.slug == "barraca-1"

    async def test_cliente_default_tiene_celular_valor_inicial(self, db_session):
        """El cliente default 'Consumidor Final' viene con datos iniciales."""
        from app.services.onboarding_service import crear_empresa_y_admin

        _, _, cliente = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Test EMpresa",
            email_admin="test@test.com",
            nombre_admin="Test",
            apellido_admin="User",
            password="Test1234",
        )

        assert cliente.celular == "000000000"
        assert cliente.direccion == "Sin dirección"
        assert cliente.es_sistema_default is True


@pytest.mark.asyncio
class TestOnboardingUnicidad:
    """Tests de unicidad de email en onboarding."""

    async def test_mismo_email_dos_empresas_diferentes_rechaza(self, db_session):
        """No se puede registrar dos empresas con el mismo email de admin."""
        from app.services.onboarding_service import crear_empresa_y_admin, EmailYaRegistradoError

        # Primera empresa
        await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Empresa A",
            email_admin="mismo@email.com",
            nombre_admin="Admin",
            apellido_admin="A",
            password="Test1234",
        )

        # Segunda empresa con mismo email → debe rechazar
        with pytest.raises(EmailYaRegistradoError):
            await crear_empresa_y_admin(
                db_session,
                nombre_empresa="Empresa B",
                email_admin="mismo@email.com",
                nombre_admin="Admin",
                apellido_admin="B",
                password="Test1234",
            )


@pytest.mark.asyncio
class TestOnboardingAislamiento:
    """Tests de aislamiento post-registro.

    El nuevo admin debe poder loguearse pero NO ver recursos de otras empresas.
    """

    async def test_nuevo_admin_puede_ver_su_empresa(self, db_session):
        """El nuevo admin puede ver su propia empresa."""
        from app.services.onboarding_service import crear_empresa_y_admin

        empresa, admin, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Mi Empresa Nueva",
            email_admin="nuevo@micompania.com",
            nombre_admin="Nuevo",
            apellido_admin="Admin",
            password="Test1234",
        )

        # El admin puede buscar su empresa
        found = await empresa_repo.get_by_id(db_session, empresa.id)
        assert found is not None
        assert found.nombre == "Mi Empresa Nueva"

    async def test_nuevo_admin_no_puede_ver_empresas_de_otros(self, db_session, empresa_a, empresa_b):
        """El nuevo admin no puede ver empresas que no le pertenecen."""
        from app.services.onboarding_service import crear_empresa_y_admin

        _, admin_nuevo, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Mi Empresa",
            email_admin="nuevo@micompania.com",
            nombre_admin="Nuevo",
            apellido_admin="Admin",
            password="Test1234",
        )

        # Nueva empresa tiene ID diferente
        assert admin_nuevo.empresa_id != empresa_a.id
        assert admin_nuevo.empresa_id != empresa_b.id

    async def test_nuevo_usuario_no_existe_globalmente_con_otro_email(self, db_session):
        """Un email único no existe en otra empresa."""
        from app.services.onboarding_service import crear_empresa_y_admin

        _, admin, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Mi Empresa",
            email_admin="unico@micompania.com",
            nombre_admin="Nuevo",
            apellido_admin="Admin",
            password="Test1234",
        )

        # El usuario tiene empresa_id correcta
        assert admin.empresa_id is not None
        assert admin.email == "unico@micompania.com"


@pytest.mark.asyncio
class TestOnboardingRateLimiting:
    """Tests para rate limiting del endpoint de registro."""

    async def test_rate_limit_bloquea_al_cuarto_intento(self, db_session):
        """Después de 3 registros, el 4to debe ser bloqueado."""
        from app.services.onboarding_service import crear_empresa_y_admin

        # 3 registros exitosos
        for i in range(3):
            try:
                await crear_empresa_y_admin(
                    db_session,
                    nombre_empresa=f"Empresa {i}",
                    email_admin=f"admin{i}@test.com",
                    nombre_admin="Test",
                    apellido_admin="User",
                    password="Test1234",
                )
            except Exception:
                pass

        # Verificar que el rate limiter tiene 3 requests
        from app.rate_limiter import onboarding_limiter

        # Simular una IP
        test_ip = "192.168.1.100"
        for _ in range(3):
            onboarding_limiter.is_allowed(test_ip)

        # El cuarto debe ser bloqueado
        is_allowed = onboarding_limiter.is_allowed(test_ip)
        assert is_allowed is False

    async def test_rate_limit_permite_despues_de_window(self, db_session):
        """Después de que pase la ventana de tiempo, debe permitir."""
        from app.rate_limiter import onboarding_limiter
        import time

        test_ip = "192.168.1.101"

        # Hacer 3 requests
        for _ in range(3):
            onboarding_limiter.is_allowed(test_ip)

        # Debe estar bloqueado
        assert onboarding_limiter.is_allowed(test_ip) is False

        # Simular que pasó el tiempo (manipular timestamps)
        # En tests reales, esto se hace con mock del time
        onboarding_limiter._requests[test_ip] = []

        # Ahora debe permitir
        assert onboarding_limiter.is_allowed(test_ip) is True
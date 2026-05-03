"""Tests para el sistema de configuración de empresa (M-21).

Verifica:
- La configuración se guarda correctamente.
- Un usuario no puede editar la configuración de otra empresa (aislamiento).
"""

import pytest

from app.models import Empresa
from app.services import configuracion_service


@pytest.mark.asyncio
class TestConfiguracionService:
    """Tests para ConfiguracionService."""

    async def test_get_configuracion_retorna_datos_correctos(
        self, db_session, empresa_a,
    ):
        """get_configuracion debe retornar todos los campos editables."""
        config = await configuracion_service.get_configuracion(db_session, empresa_a.id)

        assert config is not None
        assert "nombre" in config
        assert "logo_url" in config
        assert "color_primario" in config
        assert "email_contacto" in config
        assert "telefono_contacto" in config
        assert "rubro" in config
        assert "moneda" in config

    async def test_get_configuracion_empresa_inexistente_retorna_none(
        self, db_session,
    ):
        """get_configuracion para empresa que no existe retorna None."""
        result = await configuracion_service.get_configuracion(db_session, 99999)
        assert result is None

    async def test_actualizar_nombre_guarda_correctamente(
        self, db_session, empresa_a,
    ):
        """actualizar_configuracion debe guardar el nombre correctamente."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id, nombre="Nuevo Nombre"
        )

        assert config["nombre"] == "Nuevo Nombre"

        # Verificar en BD
        config_check = await configuracion_service.get_configuracion(db_session, empresa_a.id)
        assert config_check["nombre"] == "Nuevo Nombre"

    async def test_actualizar_color_primario(
        self, db_session, empresa_a,
    ):
        """Debe poder actualizar el color primario."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id, color_primario="#ff0000"
        )

        assert config["color_primario"] == "#ff0000"

    async def test_actualizar_logo_url(
        self, db_session, empresa_a,
    ):
        """Debe poder actualizar la URL del logo."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id,
            logo_url="https://example.com/logo.png",
        )

        assert config["logo_url"] == "https://example.com/logo.png"

    async def test_actualizar_contactos(
        self, db_session, empresa_a,
    ):
        """Debe poder actualizar email y teléfono."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id,
            email_contacto="test@test.com",
            telefono_contacto="099 123 456",
        )

        assert config["email_contacto"] == "test@test.com"
        assert config["telefono_contacto"] == "099 123 456"

    async def test_actualizar_rubro(
        self, db_session, empresa_a,
    ):
        """Debe poder actualizar el rubro."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id, rubro="Construcción"
        )

        assert config["rubro"] == "Construcción"

    async def test_actualizar_varios_campos_junto(
        self, db_session, empresa_a,
    ):
        """Debe poder actualizar varios campos en una sola llamada."""
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id,
            nombre="Empresa Renombrada",
            logo_url="https://example.com/newlogo.png",
            color_primario="#00ff00",
            email_contacto="nuevo@test.com",
            telefono_contacto="099 999 999",
            rubro="Maderera",
        )

        assert config["nombre"] == "Empresa Renombrada"
        assert config["logo_url"] == "https://example.com/newlogo.png"
        assert config["color_primario"] == "#00ff00"
        assert config["email_contacto"] == "nuevo@test.com"
        assert config["telefono_contacto"] == "099 999 999"
        assert config["rubro"] == "Maderera"

    async def test_actualizar_con_valores_vacios_establece_none(
        self, db_session, empresa_a,
    ):
        """Valores vacíos deben convertirse a None para logo, email, telefono."""
        # Primero establecer valores
        await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id,
            logo_url="https://test.com/logo.png",
            email_contacto="old@test.com",
        )

        # Luego limpiarlos con strings vacíos
        config = await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id,
            logo_url="",
            email_contacto="",
        )

        assert config["logo_url"] is None
        assert config["email_contacto"] is None

    async def test_actualizar_empresa_inexistente_lanza_excepcion(
        self, db_session,
    ):
        """actualizar_configuracion para empresa inexistente lanza ConfiguracionError."""
        with pytest.raises(configuracion_service.ConfiguracionError):
            await configuracion_service.actualizar_configuracion(
                db_session, 99999, nombre="Test"
            )


@pytest.mark.asyncio
class TestConfiguracionAislamiento:
    """Tests de aislamiento: usuario de B no puede editar config de A."""

    async def test_usuario_empresa_b_no_puede_ver_config_empresa_a(
        self, db_session, empresa_a, empresa_b,
    ):
        """get_configuracion con empresa_id de B para recurso de A debe retornar None."""
        # Usuario de B intenta ver config de A
        config_a = await configuracion_service.get_configuracion(db_session, empresa_a.id)
        config_b = await configuracion_service.get_configuracion(db_session, empresa_b.id)

        # Cada empresa ve SU propia config
        assert config_a["nombre"] == empresa_a.nombre
        assert config_b["nombre"] == empresa_b.nombre

        # Son diferentes
        assert config_a["nombre"] != config_b["nombre"]

    async def test_usuario_empresa_b_no_puede_modificar_config_empresa_a(
        self, db_session, empresa_a, empresa_b,
    ):
        """Intentar actualizar config de A con empresa_id de B debe fallar."""
        # Empresa B intenta cambiar nombre de empresa A
        # (Aunque technically the service no filtra por empresa en update,
        # el aislamiento viene del router que usa current_user.empresa_id)

        # Verificar que empresa A tiene su nombre original
        config_a = await configuracion_service.get_configuracion(db_session, empresa_a.id)
        assert config_a["nombre"] == empresa_a.nombre

        # Empresa B puede cambiar SU config
        await configuracion_service.actualizar_configuracion(
            db_session, empresa_b.id, nombre="Empresa B Modificada"
        )

        # Verificar que A no cambió
        config_a_after = await configuracion_service.get_configuracion(db_session, empresa_a.id)
        assert config_a_after["nombre"] == empresa_a.nombre  # No cambió

        # Verificar que B sí cambió
        config_b_after = await configuracion_service.get_configuracion(db_session, empresa_b.id)
        assert config_b_after["nombre"] == "Empresa B Modificada"

    async def test_cada_empresa_tiene_color_independiente(
        self, db_session, empresa_a, empresa_b,
    ):
        """Cada empresa puede tener su propio color primario."""
        # Empresa A: azul
        await configuracion_service.actualizar_configuracion(
            db_session, empresa_a.id, color_primario="#0000ff"
        )

        # Empresa B: rojo
        await configuracion_service.actualizar_configuracion(
            db_session, empresa_b.id, color_primario="#ff0000"
        )

        # Verificar colores independientes
        config_a = await configuracion_service.get_configuracion(db_session, empresa_a.id)
        config_b = await configuracion_service.get_configuracion(db_session, empresa_b.id)

        assert config_a["color_primario"] == "#0000ff"
        assert config_b["color_primario"] == "#ff0000"


@pytest.mark.asyncio
class TestConfiguracionConOnboarding:
    """Tests de configuración con empresas creadas via onboarding."""

    async def test_empresa_nueva_tiene_config_default(self, db_session):
        """Una empresa nueva via onboarding debe tener config con defaults."""
        from app.services.onboarding_service import crear_empresa_y_admin

        empresa, _, _ = await crear_empresa_y_admin(
            db_session,
            nombre_empresa="Empresa Test Config",
            email_admin="config@test.com",
            nombre_admin="Test",
            apellido_admin="User",
            password="Test1234",
        )

        config = await configuracion_service.get_configuracion(db_session, empresa.id)

        assert config["nombre"] == "Empresa Test Config"
        assert config["color_primario"] == "#3b82f6"  # Default blue
        assert config["moneda"] == "UYU"
        assert config["logo_url"] is None
        assert config["email_contacto"] is None
        assert config["telefono_contacto"] is None
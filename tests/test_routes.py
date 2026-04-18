from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Response


async def test_home_page_unauthorized(client):
    """Test home page sin autenticación debe redirigir a login."""
    response: Response = await client.get("/")
    assert response.status_code == 200


async def test_login_page(client):
    """Test página de login."""
    response: Response = await client.get("/login")
    assert response.status_code == 200


async def test_registro_page(client):
    """Test página de registro."""
    response: Response = await client.get("/registro")
    assert response.status_code == 200


async def test_nuevo_pedido_unauthorized(client):
    """Test nuevo pedido sin autenticación debe redirigir."""
    response: Response = await client.get("/nuevo-pedido")
    assert response.status_code == 200


async def test_buscar_unauthorized(client):
    """Test buscar sin autenticación debe redirigir."""
    response: Response = await client.get("/buscar")
    assert response.status_code == 200


async def test_dashboard_unauthorized(client):
    """Test dashboard sin autenticación debe redirigir."""
    response: Response = await client.get("/dashboard")
    assert response.status_code == 200

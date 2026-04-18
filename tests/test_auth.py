from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Response


async def test_register_user(client):
    """Test registro de nuevo usuario."""
    response: Response = await client.post(
        "/api/registro",
        data={
            "email": "newuser@example.com",
            "nombre": "New",
            "apellido": "User",
            "password": "NewPassword123!",
        },
    )
    assert response.status_code == 200


async def test_register_duplicate_email(client, test_user):
    """Test registro con email duplicado debe fallar."""
    response: Response = await client.post(
        "/api/registro",
        data={
            "email": test_user.email,
            "nombre": "Another",
            "apellido": "User",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200
    assert "ya está registrado" in response.text


async def test_login_success(client, test_user):
    """Test login exitoso."""
    response: Response = await client.post(
        "/api/login",
        data={
            "email": test_user.email,
            "password": "Test123!",
        },
    )
    assert response.status_code == 200


async def test_login_wrong_password(client, test_user):
    """Test login con contraseña incorrecta."""
    response: Response = await client.post(
        "/api/login",
        data={
            "email": test_user.email,
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 200
    assert "incorrectos" in response.text


async def test_login_nonexistent_user(client):
    """Test login con usuario inexistente."""
    response: Response = await client.post(
        "/api/login",
        data={
            "email": "nonexistent@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200
    assert "incorrectos" in response.text


async def test_logout_with_token(client, test_token):
    """Test logout con token válido."""
    response: Response = await client.post(
        "/api/logout",
        cookies={"access_token": test_token},
    )
    assert response.status_code == 200

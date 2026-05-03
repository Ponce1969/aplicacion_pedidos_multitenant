"""Dependencias de autenticación para FastAPI.

Reemplaza al AuthMiddleware (BaseHTTPMiddleware) que causaba
RuntimeError: Response content longer than Content-Length.

Las dependencias de FastAPI son nativas, estables y no manipulan
el stream de respuesta.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException


class AuthRequiredException(Exception):
    """Excepción personalizada para redirigir al login cuando falta token."""

    pass


PUBLIC_PATHS: set[str] = {
    "/login",
    "/registro",
    "/static",
    "/health",
    "/forgot-password",
    "/reset-password",
}

PUBLIC_PREFIXES: set[str] = {
    "/api/login",
    "/api/registro",
    "/api/logout",
    "/api/refresh-token",
    "/api/forgot-password",
    "/api/reset-password",
    "/api/onboarding",
    "/static",
}


async def require_auth(request: Request) -> None:
    """Dependency que verifica autenticación en cada request.

    Si la ruta es pública o tiene el password de Swagger, permite el acceso.
    Si no hay token JWT, lanza AuthRequiredException que el handler
    convierte en redirect a /login (o 401 para APIs).
    """
    path: str = request.url.path

    # 1. Swagger con password
    from app.config import settings

    if settings.SWAGGER_PASSWORD:
        if (
            path.startswith(f"/docs/{settings.SWAGGER_PASSWORD}")
            or path.startswith(f"/openapi.json/{settings.SWAGGER_PASSWORD}")
            or path.startswith(f"/redoc/{settings.SWAGGER_PASSWORD}")
        ):
            return
    else:
        if path in {"/docs", "/redoc", "/openapi.json"}:
            return

    # 2. Rutas públicas
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return

    # 3. Verificar token
    token: str | None = request.cookies.get("access_token")
    if not token:
        auth_header: str | None = request.headers.get("Authorization")
        if auth_header is not None and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise AuthRequiredException()

    return

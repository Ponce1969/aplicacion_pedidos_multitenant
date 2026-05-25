from collections.abc import Callable
from typing import ClassVar

from fastapi import Request, status
from jose import JWTError, jwt
from starlette.responses import RedirectResponse, Response

from app.config import settings


class AuthMiddleware:
    """Middleware para proteger rutas automáticamente.

    Verifica la presencia de un token JWT en cookies o headers.
    Las rutas públicas se definen en PUBLIC_PATHS.
    No valida el token (eso lo hace get_current_user en cada ruta),
    solo verifica que exista para redirigir al login si falta.
    También redirige a repartidores que intentan acceder a páginas restringidas.
    """

    PUBLIC_PATHS: ClassVar[set[str]] = {
        "/login",
        "/registro",
        "/static",
        "/health",
        "/forgot-password",
        "/reset-password",
    }

    PUBLIC_PREFIXES: ClassVar[set[str]] = {
        "/api/login",
        "/api/registro",
        "/api/logout",
        "/api/refresh-token",
        "/api/forgot-password",
        "/api/reset-password",
        "/api/onboarding",
        "/api/onboarding/register",
        "/static",
    }

    # Rutas que el repartidor SÍ puede acceder
    REPARTIDOR_ALLOWED_PATHS: ClassVar[set[str]] = {
        "/mis-entregas",
        "/api/pedido",  # para cambiar estado desde mis-entregas
    }

    REPARTIDOR_ALLOWED_PREFIXES: ClassVar[set[str]] = {
        "/api/pedido/",
    }

    def __init__(self, app: Callable) -> None:
        self.app = app

    def _get_user_role(self, request: Request) -> str | None:
        """Extrae el rol del JWT sin validación completa."""
        token: str | None = request.cookies.get("access_token")
        if not token:
            auth_header: str | None = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            return None
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload.get("role")
        except (JWTError, KeyError):
            return None

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path: str = request.url.path

        # Allow swagger/redoc/openapi only if password in URL matches SWAGGER_PASSWORD env var
        if settings.SWAGGER_PASSWORD:
            if (
                path.startswith(f"/docs/{settings.SWAGGER_PASSWORD}")
                or path.startswith(f"/openapi.json/{settings.SWAGGER_PASSWORD}")
                or path.startswith(f"/redoc/{settings.SWAGGER_PASSWORD}")
            ):
                await self.app(scope, receive, send)
                return
        else:
            if path in {"/docs", "/redoc", "/openapi.json"}:
                await self.app(scope, receive, send)
                return

        # Verificar si es ruta pública (exacta o por prefijo)
        is_public: bool = path in self.PUBLIC_PATHS or any(
            path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES
        )

        if not is_public:
            token: str | None = request.cookies.get("access_token")
            if not token:
                auth_header: str | None = request.headers.get("Authorization")
                if auth_header is not None and auth_header.startswith("Bearer "):
                    token = auth_header[7:]

            if not token:
                if request.headers.get("HX-Request") == "true":
                    response = RedirectResponse(
                        url="/login", status_code=status.HTTP_302_FOUND
                    )
                    response.headers["HX-Redirect"] = "/login"
                    await response(scope, receive, send)
                    return
                response = RedirectResponse(
                    url="/login", status_code=status.HTTP_302_FOUND
                )
                await response(scope, receive, send)
                return

            # Restringir repartidores: solo pueden acceder a /mis-entregas y APIs de pedidos
            role = self._get_user_role(request)
            if role == "repartidor":
                is_allowed = (
                    path in self.REPARTIDOR_ALLOWED_PATHS
                    or any(path.startswith(prefix) for prefix in self.REPARTIDOR_ALLOWED_PREFIXES)
                )
                if not is_allowed:
                    response = RedirectResponse(
                        url="/mis-entregas", status_code=status.HTTP_303_SEE_OTHER
                    )
                    await response(scope, receive, send)
                    return

        await self.app(scope, receive, send)

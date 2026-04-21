from collections.abc import Callable
from typing import ClassVar

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse, Response


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware para proteger rutas automáticamente.

    Verifica la presencia de un token JWT en cookies o headers.
    Las rutas públicas se definen en PUBLIC_PATHS.
    No valida el token (eso lo hace get_current_user en cada ruta),
    solo verifica que exista para redirigir al login si falta.
    """

    PUBLIC_PATHS: ClassVar[set[str]] = {
        "/login",
        "/registro",
        "/static",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
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
        "/static",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Callable[[], Response]],
    ) -> Response:
        path: str = request.url.path

        # Verificar si es ruta pública (exacta o por prefijo)
        is_public: bool = path in self.PUBLIC_PATHS or any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES)

        if not is_public:
            # Buscar token en cookie o header
            token: str | None = request.cookies.get("access_token")
            if not token:
                auth_header: str | None = request.headers.get("Authorization")
                if auth_header is not None and auth_header.startswith("Bearer "):
                    token = auth_header[7:]

            if not token:
                # HTMX request → redirigir con HX-Redirect header
                if request.headers.get("HX-Request") == "true":
                    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
                    redirect_response.headers["HX-Redirect"] = "/login"
                    return redirect_response
                return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

        response: Response = await call_next(request)
        return response

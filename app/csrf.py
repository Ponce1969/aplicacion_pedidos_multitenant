"""CSRF protection middleware para FastAPI.

Genera y valida tokens CSRF para proteger formularios POST.
Compatible con HTMX usando header X-CSRF-Token.
"""

import secrets
from collections.abc import Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

CSRF_EXEMPT_PATHS = {
    "/api/login",
    "/api/refresh-token",
    "/api/logout",
    "/health",
    "/static",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/cleanup-blacklist",
}


def generate_csrf_token() -> str:
    """Genera un token CSRF seguro."""
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware que genera token CSRF en GET y lo valida en POST/PUT/DELETE."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Callable[[], Response]],
    ) -> Response:
        if request.method in SAFE_METHODS:
            response = await call_next(request)

            # Generar token CSRF si no existe
            if not request.cookies.get("csrf_token"):
                new_token = generate_csrf_token()
                response.set_cookie(
                    key="csrf_token",
                    value=new_token,
                    httponly=False,  # HTMX necesita leerlo via JS
                    secure=True,
                    samesite="lax",
                    max_age=3600,
                )

            return response

        path = request.url.path

        if path in CSRF_EXEMPT_PATHS or any(
            path.startswith(prefix) for prefix in ("/api/login", "/api/refresh-token", "/api/logout")
        ):
            return await call_next(request)

        token_header = request.headers.get("X-CSRF-Token")
        token_cookie = request.cookies.get("csrf_token")

        if not token_cookie:
            response = Response(status_code=status.HTTP_403_FORBIDDEN)
            response.body = b'{"detail": "CSRF token missing"}'
            return response

        if token_header != token_cookie:
            response = Response(status_code=status.HTTP_403_FORBIDDEN)
            response.body = b'{"detail": "CSRF token invalid"}'
            return response

        return await call_next(request)

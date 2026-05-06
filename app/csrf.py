"""CSRF protection middleware para FastAPI.

Genera y valida tokens CSRF para proteger formularios POST.
Compatible con HTMX usando header X-CSRF-Token.
Versión Pure ASGI para evitar bug de Content-Length.

Rutas exentas:
- /api/login, /api/refresh-token, /api/logout: autenticación (protegidas por JWT)
- /api/onboarding/*: registro inicial (sin cookie CSRF todavía)
- /api/forgot-password, /api/reset-password: recovery (posible sin sesión)
- /api/registro: registro interno (requiere admin, pero sin CSRF previo)
- /health, /static, /docs, /openapi.json, /redoc: no tienen POST
"""

import secrets

from fastapi import Request

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Rutas que NO requieren CSRF (autenticación, registro, APIs sin browser)
CSRF_EXEMPT_PREFIXES = (
    "/api/login",
    "/api/refresh-token",
    "/api/logout",
    "/api/onboarding",
    "/api/forgot-password",
    "/api/reset-password",
    "/api/registro",
    "/static",
    "/docs/",
    "/openapi.json/",
    "/redoc/",
)

CSRF_EXEMPT_EXACT = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/cleanup-blacklist",
}


def generate_csrf_token() -> str:
    """Genera un token CSRF seguro."""
    return secrets.token_urlsafe(32)


class CSRFMiddleware:
    """Middleware que genera token CSRF en GET y lo valida en POST/PUT/DELETE.
    
    Versión Pure ASGI.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        method = request.method
        path = request.url.path

        if method in SAFE_METHODS:
            # Generar token CSRF si no existe
            if not request.cookies.get("csrf_token"):
                new_token = generate_csrf_token()
                # Modificar headers de respuesta para setear cookie
                async def wrapped_send(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        cookie_value = (
                            f"csrf_token={new_token}; Path=/; Max-Age=3600; "
                            f"Secure; SameSite=Lax"
                        )
                        headers.append((b"set-cookie", cookie_value.encode()))
                        message["headers"] = headers
                    await send(message)
                await self.app(scope, receive, wrapped_send)
                return
            await self.app(scope, receive, send)
            return

        # Verificar si la ruta está exenta de CSRF
        if path in CSRF_EXEMPT_EXACT or any(
            path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES
        ):
            await self.app(scope, receive, send)
            return

        # Para el resto de POST/PUT/DELETE, validar CSRF token
        token_header = request.headers.get("X-CSRF-Token")
        token_cookie = request.cookies.get("csrf_token")

        # Doble validación: CSRF token O Origin válido
        origin = request.headers.get("origin") or request.headers.get("referer", "")
        allowed_origins = ("pedidos-generales.loquinto.com", "localhost", "127.0.0.1")
        origin_valid = any(allowed in origin for allowed in allowed_origins)

        if not token_cookie and not origin_valid:
            body = b'{"detail":"CSRF token missing"}'
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        if token_cookie and token_header and token_header != token_cookie:
            body = b'{"detail":"CSRF token invalid"}'
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)

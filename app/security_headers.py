"""Security headers middleware para FastAPI.

Inyecta headers de seguridad en todas las respuestas HTTP.
Versión Pure ASGI para evitar bug de Content-Length de BaseHTTPMiddleware.
"""

from typing import ClassVar

from fastapi import Request


class SecurityHeadersMiddleware:
    """Agrega headers de seguridad a todas las respuestas."""

    SECURITY_HEADERS: ClassVar[dict[str, str]] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        ),
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "X-XSS-Protection": "0",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    # Headers para rutas dinámicas solamente (no estáticos)
    DYNAMIC_ONLY_HEADERS: ClassVar[set[str]] = {"Cache-Control", "Pragma"}

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        is_static = request.url.path.startswith("/static/")

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                existing = {h[0].decode(): h[1].decode() for h in headers}
                for key, value in self.SECURITY_HEADERS.items():
                    # Skip cache headers for static files — nginx handles them
                    if is_static and key in self.DYNAMIC_ONLY_HEADERS:
                        continue
                    if key not in existing:
                        headers.append((key.encode(), value.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped_send)


"""Security headers middleware para FastAPI.

Inyecta headers de seguridad en todas las respuestas HTTP.
Versión Pure ASGI para evitar bug de Content-Length de BaseHTTPMiddleware.
"""


class SecurityHeadersMiddleware:
    """Agrega headers de seguridad a todas las respuestas."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        ),
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "X-XSS-Protection": "0",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                # Agregar headers de seguridad
                existing = {h[0].decode(): h[1].decode() for h in headers}
                for key, value in self.SECURITY_HEADERS.items():
                    if key not in existing:
                        headers.append((key.encode(), value.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped_send)

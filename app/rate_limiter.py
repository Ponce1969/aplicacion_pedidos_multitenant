"""Rate limiting middleware para FastAPI.

Implementa token bucket por IP para prevenir brute force.
Versión Pure ASGI para evitar bug de Content-Length.
"""

import time
from collections import defaultdict

from fastapi import Request


class RateLimiter:
    """Token bucket por IP para rate limiting."""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        # Limpiar requests viejas
        self._requests[ip] = [ts for ts in self._requests[ip] if ts > cutoff]

        if len(self._requests[ip]) >= self.max_requests:
            return False

        self._requests[ip].append(now)
        return True

    def cleanup(self) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        keys_to_remove = []
        for ip, timestamps in self._requests.items():
            self._requests[ip] = [ts for ts in timestamps if ts > cutoff]
            if not self._requests[ip]:
                keys_to_remove.append(ip)
        for key in keys_to_remove:
            del self._requests[key]


# Instancias para diferentes endpoints
login_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_limiter = RateLimiter(max_requests=3, window_seconds=300)
forgot_password_limiter = RateLimiter(max_requests=3, window_seconds=300)
onboarding_limiter = RateLimiter(max_requests=3, window_seconds=600)

PATH_LIMITERS: dict[str, RateLimiter] = {
    "/api/login": login_limiter,
    "/api/registro": register_limiter,
    "/api/forgot-password": forgot_password_limiter,
    "/api/onboarding/register": onboarding_limiter,
}


class RateLimitMiddleware:
    """Middleware que aplica rate limiting en endpoints sensibles.
    
    Versión Pure ASGI para evitar bug de Content-Length.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path

        limiter = PATH_LIMITERS.get(path)
        if limiter is None:
            await self.app(scope, receive, send)
            return

        client_ip = request.client.host if request.client else "unknown"

        if not limiter.is_allowed(client_ip):
            body = b'{"detail":"Demasiados intentos. Esper\u00e1 unos minutos antes de intentar de nuevo."}'
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)

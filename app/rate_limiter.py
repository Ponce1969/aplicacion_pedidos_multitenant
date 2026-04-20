"""Rate limiting middleware para FastAPI.

Implementa token bucket por IP para prevenir brute force.
No requiere dependencias externas.
"""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


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

PATH_LIMITERS: dict[str, RateLimiter] = {
    "/api/login": login_limiter,
    "/api/registro": register_limiter,
    "/api/forgot-password": forgot_password_limiter,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware que aplica rate limiting en endpoints sensibles."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Callable[[], Response]],
    ) -> Response:
        path = request.url.path

        limiter = PATH_LIMITERS.get(path)
        if limiter is None:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        if not limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Demasiados intentos. Esperá unos minutos antes de intentar de nuevo."},
            )

        return await call_next(request)

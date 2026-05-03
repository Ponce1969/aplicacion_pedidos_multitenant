import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Routers
from app.api.routers import admin, auth, dashboard, pedidos, onboarding, configuracion
from app.auth import get_current_admin_user, get_password_hash
from app.config import settings
from app.database import get_db, init_db
from app.dependencies import AuthRequiredException, require_auth
from app.models import TokenBlacklist, Usuario
from app.rate_limiter import RateLimitMiddleware
from app.security_headers import SecurityHeadersMiddleware
from app.csrf import CSRFMiddleware
from app.csrf import CSRFMiddleware

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

if settings.DEBUG:
    logger.warning("DEBUG mode enabled — not for production use")


def _generate_secure_password() -> str:
    """Genera contraseña segura de 16 caracteres para admin default."""
    return secrets.token_urlsafe(16)


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Startup: crear tablas, empresa default y usuario admin."""
    await init_db()

    async for db in get_db():
        # Asegurar empresa default
        from app.models import Empresa  # noqa: PLC0415

        empresa_result = await db.execute(select(Empresa).where(Empresa.slug == "default"))
        empresa: Empresa | None = empresa_result.scalar_one_or_none()
        if empresa is None:
            empresa = Empresa(nombre="Mi Empresa", slug="default", rubro="General")
            db.add(empresa)
            await db.commit()
            await db.refresh(empresa)

        # Crear admin si no existe
        # Crear admin si no existe, o actualizar si falta campos
        admin_query = select(Usuario).where(Usuario.email == "admin@barraca.com")
        admin_result = await db.execute(admin_query)
        admin_user: Usuario | None = admin_result.scalar_one_or_none()

        if admin_user is None:
            admin_password = _generate_secure_password()
            new_admin = Usuario(
                email="admin@barraca.com",
                nombre="Admin",
                apellido="Sistema",
                password_hash=get_password_hash(admin_password),
                is_admin=True,
                empresa_id=empresa.id,
            )
            db.add(new_admin)
            await db.commit()
            logger.warning(
                "Admin user created: email=admin@barraca.com, password=%s — CHANGE IMMEDIATELY",
                admin_password,
            )
        elif admin_user.empresa_id is None:
            admin_user.empresa_id = empresa.id
            await db.commit()
            logger.info("Updated admin user with empresa_id=%s", empresa.id)
        break

    logger.info("Database initialized")

    # Background task: cleanup de tokens expirados cada 6 horas
    async def _cleanup_blacklist_periodically() -> None:
        while True:
            await asyncio.sleep(6 * 60 * 60)  # 6 horas
            try:
                async for db in get_db():
                    result = await db.execute(
                        delete(TokenBlacklist).where(TokenBlacklist.expiracion < func.now()),
                    )
                    await db.commit()
                    if result.rowcount > 0:
                        logger.info("Auto-cleaned %d expired tokens from blacklist", result.rowcount)
                    break
            except Exception as exc:
                logger.error("Blacklist cleanup failed: %s", exc)

    cleanup_task = asyncio.create_task(_cleanup_blacklist_periodically())

    yield

    cleanup_task.cancel()
    logger.info("Shutting down connections...")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url=f"/docs/{settings.SWAGGER_PASSWORD}" if settings.SWAGGER_PASSWORD else None,
    redoc_url=f"/redoc/{settings.SWAGGER_PASSWORD}" if settings.SWAGGER_PASSWORD else None,
    openapi_url=f"/openapi.json/{settings.SWAGGER_PASSWORD}" if settings.SWAGGER_PASSWORD else None,
    dependencies=[Depends(require_auth)],
)


@app.exception_handler(AuthRequiredException)
async def auth_required_handler(request: Request, exc: AuthRequiredException) -> RedirectResponse:
    """Handler para AuthRequiredException: redirige al login."""
    if request.headers.get("HX-Request") == "true":
        response = RedirectResponse(url="/login", status_code=302)
        response.headers["HX-Redirect"] = "/login"
        return response
    return RedirectResponse(url="/login", status_code=302)

# Middleware de rate limiting (primero, antes de auth)
app.add_middleware(RateLimitMiddleware)

# CSRF protection (solo en producción)
if settings.APP_ENV == "production":
    app.add_middleware(CSRFMiddleware)

# Headers de seguridad HTTP
app.add_middleware(SecurityHeadersMiddleware)

# CORS restrictivo
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.BASE_URL.rstrip("/")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Registrar routers
app.include_router(auth.router)
app.include_router(pedidos.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(onboarding.router)
app.include_router(configuracion.router)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Endpoint de health check para Docker y monitoreo."""
    return JSONResponse({"status": "ok"})


@app.post("/api/cleanup-blacklist")
async def cleanup_blacklist(
    _current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> JSONResponse:
    """Elimina tokens expirados de la blacklist.

    Debería ejecutarse periódicamente (cron o scheduler).
    Protegido: solo accesible para admins.
    """
    result = await db.execute(
        delete(TokenBlacklist).where(TokenBlacklist.expiracion < func.now()),
    )
    await db.commit()
    deleted = result.rowcount
    logger.info("Cleaned up %d expired tokens from blacklist", deleted)
    return JSONResponse({"deleted": deleted})

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select, text

# Routers
from app.api.routers import admin, auth, dashboard, pedidos
from app.auth import get_current_admin_user, get_password_hash
from app.config import settings
from app.database import get_db, init_db
from app.middlewares import AuthMiddleware
from app.models import TokenBlacklist, Usuario
from app.rate_limiter import RateLimitMiddleware
from app.security_headers import SecurityHeadersMiddleware
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
    yield
    logger.info("Shutting down connections...")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Middleware de rate limiting (primero, antes de auth)
app.add_middleware(RateLimitMiddleware)

# CSRF protection (solo en producción)
if settings.APP_ENV == "production":
    app.add_middleware(CSRFMiddleware)

# Middleware de autenticación
app.add_middleware(AuthMiddleware)

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


@app.get("/health")
async def health_check() -> JSONResponse:
    """Endpoint de health check para Docker y monitoreo."""
    return JSONResponse({"status": "ok"})


@app.post("/api/cleanup-blacklist")
async def cleanup_blacklist(
    _current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
) -> JSONResponse:
    """Elimina tokens expirados de la blacklist.

    Debería ejecutarse periódicamente (cron o scheduler).
    Protegido: solo accesible para admins.
    """
    async for db in get_db():
        result = await db.execute(
            delete(TokenBlacklist).where(TokenBlacklist.expiracion < text("NOW()")),
        )
        await db.commit()
        deleted = result.rowcount
        logger.info("Cleaned up %d expired tokens from blacklist", deleted)
        return JSONResponse({"deleted": deleted})
    return JSONResponse({"deleted": 0})

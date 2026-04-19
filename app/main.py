from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

# Routers
from app.api.routers import admin, auth, dashboard, pedidos
from app.auth import get_password_hash
from app.config import settings
from app.database import get_db, init_db
from app.middlewares import AuthMiddleware
from app.models import Usuario


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Startup: crear tablas y usuario admin por defecto."""
    await init_db()

    async for db in get_db():
        admin_query = select(Usuario).where(Usuario.email == "admin@barraca.com")
        admin_result = await db.execute(admin_query)
        admin_user: Usuario | None = admin_result.scalar_one_or_none()

        if admin_user is None:
            new_admin = Usuario(
                email="admin@barraca.com",
                nombre="Admin",
                apellido="Sistema",
                password_hash=get_password_hash("Admin123!"),
                is_admin=True,
            )
            db.add(new_admin)
            await db.commit()
            print("✅ Usuario admin creado: admin@barraca.com / Admin123!")
        break

    print("✅ Base de datos inicializada")
    yield
    print("🛑 Cerrando conexiones...")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Middleware de autenticación
app.add_middleware(AuthMiddleware)

# Archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Registrar routers
app.include_router(auth.router)
app.include_router(pedidos.router)
app.include_router(dashboard.router)
app.include_router(admin.router)

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_admin_user,
    get_current_user,
    get_password_hash,
    logout_user,
    refresh_access_token,
    verify_password,
)
from app.config import settings
from app.database import get_db, init_db
from app.middlewares import AuthMiddleware
from app.models import Pedido, Usuario


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Startup: crear tablas y usuario admin por defecto."""
    await init_db()

    async for db in get_db():
        admin_query = select(Usuario).where(Usuario.email == "admin@barraca.com")
        admin_result = await db.execute(admin_query)
        admin: Usuario | None = admin_result.scalar_one_or_none()

        if admin is None:
            admin_user = Usuario(
                email="admin@barraca.com",
                nombre="Admin",
                apellido="Sistema",
                password_hash=get_password_hash("Admin123!"),
                is_admin=True,
            )
            db.add(admin_user)
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

app.add_middleware(AuthMiddleware)

# Rutas relativas para templates y static (WORKDIR=/app, estructura: /app/app/templates/)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ==================== RUTAS PÚBLICAS ====================


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@app.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "registro.html")


@app.post("/api/registro")
async def registro(  # noqa: PLR0913 — too many args
    request: Request,
    email: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    # Verificar si email ya existe
    existing_query = select(Usuario).where(Usuario.email == email)
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none() is not None:
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": "El email ya está registrado"},
        )

    # Crear usuario
    nuevo_usuario = Usuario(
        email=email,
        nombre=nombre,
        apellido=apellido,
        password_hash=get_password_hash(password),
    )
    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)

    # Crear tokens
    access_token: str = create_access_token(data={"sub": str(nuevo_usuario.id)})
    refresh_token: str = create_refresh_token(data={"sub": str(nuevo_usuario.id)})

    # Response con cookies
    response = templates.TemplateResponse(
        request, "partials/success.html", {"mensaje": "Usuario registrado exitosamente"},
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return response


@app.post("/api/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> RedirectResponse:
    # Buscar usuario activo
    user_query = select(Usuario).where(Usuario.email == email, Usuario.is_active == True)  # noqa: E712
    user_result = await db.execute(user_query)
    user: Usuario | None = user_result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": "Email o contraseña incorrectos"},
        )

    # Actualizar último login
    user.ultimo_login = datetime.now(UTC)
    await db.commit()

    # Crear tokens
    access_token: str = create_access_token(data={"sub": str(user.id)})
    refresh_token: str = create_refresh_token(data={"sub": str(user.id)})

    # Response con cookies y redirección HTMX
    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Redirect"] = "/dashboard"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return response


@app.post("/api/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    token: str | None = request.cookies.get("access_token")
    if token is not None:
        await logout_user(token, db)

    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Redirect"] = "/login"
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@app.post("/api/refresh-token", response_model=None)
async def refresh_token_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> JSONResponse | RedirectResponse:
    refresh_token_value: str | None = request.cookies.get("refresh_token")
    if refresh_token_value is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        new_access_token: str = await refresh_access_token(refresh_token_value, db)
        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response
    except HTTPException:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response


# ==================== RUTAS PROTEGIDAS ====================


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/nuevo-pedido", response_class=HTMLResponse)
async def nuevo_pedido_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "nuevo_pedido.html",
        {
            "user": current_user,
        },
    )


@app.post("/guardar-pedido")
async def guardar_pedido(  # noqa: PLR0913 — too many args
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    celular: str = Form(...),
    direccion: str = Form(...),
    hora_entrega: str = Form(...),
    fecha_entrega: str = Form(...),
    pedido_detalle: str = Form(...),
    total: float = Form(...),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    # Convertir fecha string a datetime con timezone
    fecha_dt: datetime = datetime.strptime(fecha_entrega, "%Y-%m-%d")
    fecha_dt = fecha_dt.replace(tzinfo=UTC)

    nuevo_pedido = Pedido(
        usuario_id=current_user.id,
        nombre=nombre,
        apellido=apellido,
        celular=celular,
        direccion=direccion,
        hora_entrega=hora_entrega,
        fecha_entrega=fecha_dt,
        pedido_detalle=pedido_detalle,
        total=total,
    )

    db.add(nuevo_pedido)
    await db.commit()
    await db.refresh(nuevo_pedido)

    return templates.TemplateResponse(
        request, "partials/success.html", {"mensaje": f"✅ Pedido #{nuevo_pedido.id} guardado exitosamente"},
    )


@app.get("/buscar", response_class=HTMLResponse)
async def buscar_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "buscar.html",
        {
            "user": current_user,
        },
    )


@app.post("/buscar-pedidos")
async def buscar_pedidos(
    request: Request,
    termino: str = Form(...),
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    query = (
        select(Pedido)
        .where((Pedido.celular.contains(termino)) | (Pedido.apellido.ilike(f"%{termino}%")))
        .order_by(Pedido.fecha_creacion.desc())
    )

    result = await db.execute(query)
    pedidos: list[Pedido] = list(result.scalars().all())

    return templates.TemplateResponse(
        request, "partials/resultados_busqueda.html", {"pedidos": pedidos, "termino": termino},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    hoy: date = datetime.now(UTC).date()
    primer_dia_mes: date = hoy.replace(day=1)

    query = select(Pedido).where(Pedido.fecha_creacion >= primer_dia_mes).order_by(Pedido.fecha_creacion.desc())

    result = await db.execute(query)
    pedidos_mes: list[Pedido] = list(result.scalars().all())

    total_ventas: float = sum(pedido.total for pedido in pedidos_mes)
    cantidad_pedidos: int = len(pedidos_mes)

    # Productos más vendidos — parseo del campo pedido_detalle
    productos_vendidos: dict[str, float] = {}
    for pedido in pedidos_mes:
        try:
            lineas: list[str] = pedido.pedido_detalle.split("\n")
            for linea in lineas:
                if "-" in linea:
                    partes: list[str] = linea.split("-", 1)
                    nombre_prod: str = partes[0].strip()
                    try:
                        cantidad_str: str = partes[1].strip().replace("kg", "").replace("unidad", "").strip()
                        cantidad: float = float(cantidad_str)
                    except (ValueError, IndexError):
                        cantidad = 1.0
                    productos_vendidos[nombre_prod] = productos_vendidos.get(nombre_prod, 0.0) + cantidad
        except (AttributeError, ValueError):
            pass

    top_productos: list[tuple[str, float]] = sorted(productos_vendidos.items(), key=lambda x: x[1], reverse=True)[:5]

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "user": current_user,
            "total_ventas": total_ventas,
            "cantidad_pedidos": cantidad_pedidos,
            "top_productos": top_productos,
            "pedidos_recientes": pedidos_mes[:10],
            "mes_actual": hoy.strftime("%B %Y"),
        },
    )


@app.get("/pedido/{pedido_id}")
async def ver_pedido(
    pedido_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    query = select(Pedido).where(Pedido.id == pedido_id)
    result = await db.execute(query)
    pedido: Pedido | None = result.scalar_one_or_none()

    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    return templates.TemplateResponse(
        request, "partials/detalle_pedido.html", {"pedido": pedido, "user": current_user},
    )


# ==================== RUTAS ADMIN ====================


@app.get("/admin/usuarios", response_class=HTMLResponse)
async def listar_usuarios(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    query = select(Usuario).order_by(Usuario.fecha_creacion.desc())
    result = await db.execute(query)
    usuarios: list[Usuario] = list(result.scalars().all())

    return templates.TemplateResponse(
        request, "admin/usuarios.html", {"user": current_user, "usuarios": usuarios},
    )

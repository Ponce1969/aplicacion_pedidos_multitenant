from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    logout_user,
    refresh_access_token,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import Usuario

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@router.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "registro.html")


@router.post("/api/registro")
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


@router.post("/api/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
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


@router.post("/api/logout")
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


@router.post("/api/refresh-token", response_model=None)
async def refresh_token_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> JSONResponse | RedirectResponse:
    refresh_token_value: str | None = request.cookies.get("refresh_token")
    if refresh_token_value is None:
        from fastapi import HTTPException

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
    except Exception:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response

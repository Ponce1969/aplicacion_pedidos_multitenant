from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import refresh_access_token
from app.config import settings
from app.database import get_db
from app.services import auth_service
from app.services.password_reset_service import create_reset_token, reset_password

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
    empresa_id: int = Form(1),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    result = await auth_service.register_user(db, email, nombre, apellido, password, empresa_id)

    if isinstance(result, str):
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": result},
        )

    response = templates.TemplateResponse(
        request, "partials/success.html", {"mensaje": "Usuario registrado exitosamente"},
    )
    auth_service.build_auth_cookies(response, result.id)
    return response


@router.post("/api/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    user = await auth_service.authenticate_user(db, email, password)

    if user is None:
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": "Email o contraseña incorrectos"},
        )

    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Redirect"] = "/dashboard"
    auth_service.build_auth_cookies(response, user.id)
    return response


@router.post("/api/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    token: str | None = request.cookies.get("access_token")
    await auth_service.logout_user_service(db, token)

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    response: JSONResponse | RedirectResponse
    try:
        new_access_token: str = await refresh_access_token(refresh_token_value, db)
        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "forgot_password.html")


@router.post("/api/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    await create_reset_token(db, email)
    # Siempre mostramos el mismo mensaje para no revelar si el email existe
    return templates.TemplateResponse(
        request, "partials/success.html",
        {"mensaje": "Si el email está registrado, recibirás un link de recuperación en tu casilla."},
    )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})


@router.post("/api/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": "Las contraseñas no coinciden"},
        )

    if len(new_password) < 6:  # noqa: PLR2004 — min password length
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": "La contraseña debe tener al menos 6 caracteres"},
        )

    error = await reset_password(db, token, new_password)
    if error:
        return templates.TemplateResponse(
            request, "partials/error.html", {"error": error},
        )

    return templates.TemplateResponse(
        request, "partials/success.html",
        {"mensaje": "Contraseña actualizada. Ya podés iniciar sesión con tu nueva contraseña."},
    )

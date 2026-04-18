from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin_user
from app.database import get_db
from app.models import Usuario
from app.repositories import usuario_repo

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/usuarios", response_class=HTMLResponse)
async def listar_usuarios(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008 — FastAPI pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI pattern
) -> HTMLResponse:
    usuarios = await usuario_repo.list_all(db)

    return templates.TemplateResponse(
        request, "admin/usuarios.html", {"user": current_user, "usuarios": usuarios},
    )

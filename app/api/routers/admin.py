"""Router de administración — CRUD usuarios, configuración empresa, tabs.

Todos los endpoints devuelven HTML directo (HTMX partials o páginas completas).
No hay endpoints JSON innecesarios.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin_user, require_role
from app.database import get_db
from app.models import ROLE_ADMIN, ROLE_OWNER, VALID_ROLES, Usuario
from app.repositories import empresa_repo, usuario_repo
from app.templates_env import get_templates
from app.utils import normalizar_rut, validar_rut

logger = logging.getLogger(__name__)

router = APIRouter()
templates = get_templates()


# ==================== VISTA PRINCIPAL — TABS ====================


@router.get("/admin", response_class=HTMLResponse)
async def administracion(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Panel de administración con tabs: Empresa, Usuarios, Parámetros."""
    config = await empresa_repo.get_by_id(db, current_user.empresa_id)
    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/administracion.html",
        {
            "user": current_user,
            "config": config,
            "usuarios": usuarios,
            "active_tab": "empresa",
            "valid_roles": VALID_ROLES,
        },
    )


# ==================== TAB PARTIALS ====================


@router.get("/admin/tab/empresa", response_class=HTMLResponse)
async def tab_empresa(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """HTMX partial: tab de configuración de empresa."""
    config = await empresa_repo.get_by_id(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_empresa.html",
        {"user": current_user, "config": config, "success": False, "error": None},
    )


@router.get("/admin/tab/usuarios", response_class=HTMLResponse)
async def tab_usuarios(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """HTMX partial: tab de gestión de usuarios."""
    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_usuarios.html",
        {"user": current_user, "usuarios": usuarios, "valid_roles": VALID_ROLES},
    )


# ==================== CONFIGURACIÓN EMPRESA ====================


@router.post("/admin/configuracion/actualizar", response_class=HTMLResponse)
async def actualizar_configuracion(
    request: Request,
    nombre: str = Form(""),
    rubro: str = Form(""),
    rut: str = Form(""),
    direccion: str = Form(""),
    ciudad: str = Form(""),
    email_contacto: str = Form(""),
    telefono_contacto: str = Form(""),
    logo_url: str = Form(""),
    color_primario: str = Form("#3b82f6"),
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Actualiza la configuración de la empresa."""
    empresa = await empresa_repo.get_by_id(db, current_user.empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Normalizar y validar RUT
    rut_normalizado = normalizar_rut(rut) if rut.strip() else None
    if rut.strip() and not validar_rut(rut):
        config_data = {
            "nombre": empresa.nombre, "rut": empresa.rut,
            "direccion": empresa.direccion, "ciudad": empresa.ciudad,
            "logo_url": empresa.logo_url, "color_primario": empresa.color_primario,
            "email_contacto": empresa.email_contacto, "telefono_contacto": empresa.telefono_contacto,
            "rubro": empresa.rubro,
        }
        return templates.TemplateResponse(
            request,
            "admin/partials/tab_empresa.html",
            {"user": current_user, "config": config_data, "success": False,
             "error": f"RUT inválido: {rut}. Verificá el dígito verificador."},
        )

    # Actualizar campos
    if nombre.strip():
        empresa.nombre = nombre.strip()
    if rubro.strip():
        empresa.rubro = rubro.strip()
    else:
        empresa.rubro = None
    empresa.rut = rut_normalizado
    empresa.direccion = direccion.strip() if direccion.strip() else None
    empresa.ciudad = ciudad.strip() if ciudad.strip() else None
    empresa.email_contacto = email_contacto.strip() if email_contacto.strip() else None
    empresa.telefono_contacto = telefono_contacto.strip() if telefono_contacto.strip() else None
    empresa.logo_url = logo_url.strip() if logo_url.strip() else None
    empresa.color_primario = color_primario.strip() if color_primario.strip() else "#3b82f6"

    await db.commit()
    await db.refresh(empresa)

    config_data = {
        "nombre": empresa.nombre, "rut": empresa.rut,
        "direccion": empresa.direccion, "ciudad": empresa.ciudad,
        "logo_url": empresa.logo_url, "color_primario": empresa.color_primario,
        "email_contacto": empresa.email_contacto, "telefono_contacto": empresa.telefono_contacto,
        "rubro": empresa.rubro,
    }
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_empresa.html",
        {"user": current_user, "config": config_data, "success": True, "error": None},
    )


# ==================== CRUD USUARIOS ====================


@router.get("/admin/usuarios/nuevo", response_class=HTMLResponse)
async def nuevo_usuario_form(
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER)),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para crear un nuevo usuario. Solo owner."""
    return templates.TemplateResponse(
        request,
        "admin/partials/usuario_form.html",
        {"user": current_user, "usuario_edit": None, "valid_roles": VALID_ROLES, "error": None},
    )


@router.post("/admin/usuarios/crear", response_class=HTMLResponse)
async def crear_usuario(
    request: Request,
    email: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    password: str = Form(...),
    rol: str = Form("vendedor"),
    current_user: Usuario = Depends(require_role(ROLE_OWNER)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Crea un nuevo usuario. Solo owner."""
    from app.auth import get_password_hash

    # Validar rol
    if rol not in VALID_ROLES:
        return templates.TemplateResponse(
            request,
            "admin/partials/usuario_form.html",
            {"user": current_user, "usuario_edit": None, "valid_roles": VALID_ROLES,
             "error": f"Rol inválido: {rol}"},
        )

    # Verificar email duplicado
    existing = await usuario_repo.get_by_email(db, email.strip(), current_user.empresa_id)
    if existing:
        return templates.TemplateResponse(
            request,
            "admin/partials/usuario_form.html",
            {"user": current_user, "usuario_edit": None, "valid_roles": VALID_ROLES,
             "error": f"Ya existe un usuario con email {email}"},
        )

    nuevo = Usuario(
        empresa_id=current_user.empresa_id,
        email=email.strip().lower(),
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        password_hash=get_password_hash(password),
        rol=rol,
        is_admin=(rol in (ROLE_OWNER, ROLE_ADMIN)),
        is_active=True,
    )
    saved = await usuario_repo.create(db, nuevo)
    logger.info("Usuario #%s creado por owner #%s (rol=%s)", saved.id, current_user.id, rol)

    # Retornar la tabla actualizada de usuarios
    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_usuarios.html",
        {"user": current_user, "usuarios": usuarios, "valid_roles": VALID_ROLES},
    )


@router.get("/admin/usuarios/{user_id}/editar", response_class=HTMLResponse)
async def editar_usuario_form(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para editar un usuario."""
    usuario_edit = await usuario_repo.get_by_id(db, user_id, current_user.empresa_id)
    if usuario_edit is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return templates.TemplateResponse(
        request,
        "admin/partials/usuario_form.html",
        {"user": current_user, "usuario_edit": usuario_edit, "valid_roles": VALID_ROLES, "error": None},
    )


@router.post("/admin/usuarios/{user_id}/editar", response_class=HTMLResponse)
async def editar_usuario_guardar(
    user_id: int,
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(...),
    rol: str = Form("vendedor"),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Guarda cambios en un usuario."""
    usuario = await usuario_repo.get_by_id(db, user_id, current_user.empresa_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Solo owner puede cambiar roles
    if current_user.rol == ROLE_OWNER and rol in VALID_ROLES:
        usuario.rol = rol
        usuario.is_admin = (rol in (ROLE_OWNER, ROLE_ADMIN))

    usuario.nombre = nombre.strip()
    usuario.apellido = apellido.strip()
    usuario.email = email.strip().lower()

    await db.commit()
    await db.refresh(usuario)
    logger.info("Usuario #%s editado por %s #%s", user_id, current_user.rol, current_user.id)

    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_usuarios.html",
        {"user": current_user, "usuarios": usuarios, "valid_roles": VALID_ROLES},
    )


@router.post("/admin/usuarios/{user_id}/toggle", response_class=HTMLResponse)
async def toggle_usuario(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Activa o desactiva un usuario. Solo owner."""
    usuario = await usuario_repo.get_by_id(db, user_id, current_user.empresa_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # No desactivarse a sí mismo
    if usuario.id == current_user.id:
        raise HTTPException(status_code=400, detail="No podés desactivarte a vos mismo")

    if usuario.is_active:
        await usuario_repo.deactivate(db, user_id, current_user.empresa_id)
        logger.info("Usuario #%s desactivado por owner #%s", user_id, current_user.id)
    else:
        await usuario_repo.activate(db, user_id, current_user.empresa_id)
        logger.info("Usuario #%s reactivado por owner #%s", user_id, current_user.id)

    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_usuarios.html",
        {"user": current_user, "usuarios": usuarios, "valid_roles": VALID_ROLES},
    )


@router.post("/admin/usuarios/{user_id}/reset-password", response_class=HTMLResponse)
async def reset_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    current_user: Usuario = Depends(require_role(ROLE_OWNER)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Resetea la contraseña de un usuario. Solo owner."""
    from app.auth import get_password_hash

    usuario = await usuario_repo.get_by_id(db, user_id, current_user.empresa_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.password_hash = get_password_hash(new_password)
    await db.commit()
    logger.info("Password reset for user #%s by owner #%s", user_id, current_user.id)

    usuarios = await usuario_repo.list_all(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_usuarios.html",
        {"user": current_user, "usuarios": usuarios, "valid_roles": VALID_ROLES},
    )
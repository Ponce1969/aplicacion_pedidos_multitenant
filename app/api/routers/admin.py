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
from app.models import ROLE_ADMIN, ROLE_OWNER, VALID_ROLES, Producto, Usuario
from app.repositories import empresa_repo, producto_repo, usuario_repo
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
current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para crear un nuevo fletero. Owner y Admin."""
    return templates.TemplateResponse(
        request,
        "admin/partials/fletero_form.html",
        {"user": current_user, "fletero_edit": None, "error": None},
    )


@router.post("/admin/fleteros/crear", response_class=HTMLResponse)
async def crear_fletero(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    celular: str = Form(...),
    vehiculo: str = Form(""),
    ci: str = Form(""),
    password: str = Form(...),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Crea un nuevo fletero. Owner y Admin. Auto-genera el email."""
    from app.auth import get_password_hash
    from app.services.queries.fletero_service import get_fleteros_con_estado

    # Auto-generar email: celular@empresa-slug.com
    config = await empresa_repo.get_by_id(db, current_user.empresa_id)
    slug = config.slug if config else f"empresa{current_user.empresa_id}"
    # Normalizar celular para email: sacamos espacios, guiones, etc.
    celular_limpio = celular.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    email_autogenerado = f"{celular_limpio}@{slug}.fletero"

    # Verificar email duplicado
    existing = await usuario_repo.get_by_email(db, email_autogenerado, current_user.empresa_id)
    if existing:
        # Intentar con apellido
        email_autogenerado = f"{celular_limpio}.{apellido.strip().lower()}@{slug}.fletero"
        existing = await usuario_repo.get_by_email(db, email_autogenerado, current_user.empresa_id)
        if existing:
            return templates.TemplateResponse(
                request,
                "admin/partials/fletero_form.html",
                {"user": current_user, "fletero_edit": None,
                 "error": f"Ya existe un fletero con celular {celular}. Contactá al administrador."},
            )

    # Validar CI si se proporciona
    ci_value = ci.strip() if ci.strip() else None
    if ci_value:
        ci_normalizado = normalizar_rut(ci_value)
        if not validar_rut(ci_normalizado):
            return templates.TemplateResponse(
                request,
                "admin/partials/fletero_form.html",
                {"user": current_user, "fletero_edit": None,
                 "error": f"CI/RUT inválido: {ci_value}"},
            )
        ci_value = ci_normalizado

    nuevo = Usuario(
        empresa_id=current_user.empresa_id,
        email=email_autogenerado,
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        password_hash=get_password_hash(password),
        rol="repartidor",
        is_admin=False,
        is_active=True,
        celular=celular.strip(),
        vehiculo=vehiculo.strip() or None,
        ci=ci_value,
    )
    await usuario_repo.create(db, nuevo)
    logger.info("Fletero '%s %s' creado por owner #%s (email=%s)", nombre, apellido, current_user.id, email_autogenerado)

    fleteros = await get_fleteros_con_estado(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_fleteros.html",
        {"user": current_user, "fleteros": fleteros},
    )


@router.get("/admin/fleteros/{fletero_id}/editar", response_class=HTMLResponse)
async def editar_fletero_form(
    fletero_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para editar un fletero."""
    fletero = await usuario_repo.get_by_id(db, fletero_id, current_user.empresa_id)
    if fletero is None or fletero.rol != "repartidor":
        raise HTTPException(status_code=404, detail="Fletero no encontrado")
    return templates.TemplateResponse(
        request,
        "admin/partials/fletero_form.html",
        {"user": current_user, "fletero_edit": fletero, "error": None},
    )


@router.post("/admin/fleteros/{fletero_id}/editar", response_class=HTMLResponse)
async def editar_fletero_guardar(
    fletero_id: int,
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    celular: str = Form(...),
    vehiculo: str = Form(""),
    ci: str = Form(""),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Guarda cambios en un fletero."""
    from app.services.queries.fletero_service import get_fleteros_con_estado

    fletero = await usuario_repo.get_by_id(db, fletero_id, current_user.empresa_id)
    if fletero is None or fletero.rol != "repartidor":
        raise HTTPException(status_code=404, detail="Fletero no encontrado")

    # Validar CI si se proporciona
    ci_value = ci.strip() if ci.strip() else None
    if ci_value:
        ci_normalizado = normalizar_rut(ci_value)
        if not validar_rut(ci_normalizado):
            return templates.TemplateResponse(
                request,
                "admin/partials/fletero_form.html",
                {"user": current_user, "fletero_edit": fletero,
                 "error": f"CI/RUT inválido: {ci_value}"},
            )
        ci_value = ci_normalizado

    fletero.nombre = nombre.strip()
    fletero.apellido = apellido.strip()
    fletero.celular = celular.strip()
    fletero.vehiculo = vehiculo.strip() or None
    fletero.ci = ci_value

    await db.commit()
    await db.refresh(fletero)
    logger.info("Fletero #%s editado por owner #%s", fletero_id, current_user.id)

    fleteros = await get_fleteros_con_estado(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_fleteros.html",
        {"user": current_user, "fleteros": fleteros},
    )


@router.post("/admin/fleteros/{fletero_id}/toggle", response_class=HTMLResponse)
async def toggle_fletero(
    fletero_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Activa o desactiva un fletero (soft delete)."""
    from app.services.queries.fletero_service import get_fleteros_con_estado

    fletero = await usuario_repo.get_by_id(db, fletero_id, current_user.empresa_id)
    if fletero is None or fletero.rol != "repartidor":
        raise HTTPException(status_code=404, detail="Fletero no encontrado")

    if fletero.is_active:
        fletero.is_active = False
        logger.info("Fletero #%s desactivado por owner #%s", fletero_id, current_user.id)
    else:
        fletero.is_active = True
        logger.info("Fletero #%s reactivado por owner #%s", fletero_id, current_user.id)

    await db.commit()

    fleteros = await get_fleteros_con_estado(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_fleteros.html",
        {"user": current_user, "fleteros": fleteros},
    )


@router.post("/admin/fleteros/{fletero_id}/reset-password", response_class=HTMLResponse)
async def reset_fletero_password(
    fletero_id: int,
    request: Request,
    new_password: str = Form(...),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Resetea la contraseña de un fletero."""
    from app.auth import get_password_hash
    from app.services.queries.fletero_service import get_fleteros_con_estado

    fletero = await usuario_repo.get_by_id(db, fletero_id, current_user.empresa_id)
    if fletero is None or fletero.rol != "repartidor":
        raise HTTPException(status_code=404, detail="Fletero no encontrado")

    fletero.password_hash = get_password_hash(new_password)
    await db.commit()
    logger.info("Contraseña reseteada para fletero #%s por owner #%s", fletero_id, current_user.id)

    fleteros = await get_fleteros_con_estado(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_fleteros.html",
        {"user": current_user, "fleteros": fleteros},
    )


# ==================== EXPORTACIÓN CSV ====================


@router.get("/admin/pedidos/exportar-csv")
async def exportar_pedidos_csv(
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Exporta pedidos de la empresa a CSV."""
    import csv
    import io
    from datetime import datetime as dt

    from fastapi.responses import StreamingResponse

    from app.repositories import pedido_repo

    pedidos = await pedido_repo.list_all_for_export(db, current_user.empresa_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "N°", "Fecha", "Cliente", "Celular", "CI", "Dirección",
        "Total", "Seña", "Saldo", "Estado", "Estado Pago",
        "Items",
    ])

    for p in pedidos:
        items_str = "; ".join(
            f"{i.descripcion} x{i.cantidad} @ {i.precio_unitario}" for i in p.items
        )
        saldo = (p.total or 0) - (p.senia or 0)
        writer.writerow([
            p.numero_pedido,
            p.fecha_creacion.strftime("%d/%m/%Y %H:%M") if p.fecha_creacion else "",
            f"{p.nombre} {p.apellido}",
            p.celular,
            p.ci or "",
            p.direccion,
            p.total or 0,
            p.senia or 0,
            saldo,
            p.estado,
            p.estado_pago,
            items_str,
        ])

    output.seek(0)
    filename = f"pedidos_{dt.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
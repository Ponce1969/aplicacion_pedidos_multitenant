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
    """Muestra formulario para crear un nuevo usuario. Owner y Admin."""
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
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Crea un nuevo usuario. Owner y Admin."""
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
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Activa o desactiva un usuario. Owner y Admin."""
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


# ==================== CATÁLOGO DE PRODUCTOS ====================


@router.get("/admin/tab/catalogo", response_class=HTMLResponse)
async def tab_catalogo(
    request: Request,
    q: str = "",
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """HTMX partial: tab de catálogo de productos."""
    if q and len(q) >= 2:
        all_prods = await producto_repo.list_all(db, current_user.empresa_id, include_inactive=True)
        productos = [p for p in all_prods if q.lower() in p.nombre.lower() or (p.sku and q.lower() in p.sku.lower())]
    else:
        productos = await producto_repo.list_all(db, current_user.empresa_id, include_inactive=True)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_catalogo.html",
        {"user": current_user, "productos": productos, "q": q},
    )


@router.get("/admin/productos/nuevo", response_class=HTMLResponse)
async def nuevo_producto_form(
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para crear un nuevo producto."""
    return templates.TemplateResponse(
        request,
        "admin/partials/producto_form.html",
        {"user": current_user, "producto": None, "error": None},
    )


@router.post("/admin/productos/crear", response_class=HTMLResponse)
async def crear_producto(
    request: Request,
    nombre: str = Form(...),
    sku: str = Form(""),
    precio_base: float = Form(0),
    unidad_medida: str = Form("unidad"),
    stock: str = Form(""),
    descripcion: str = Form(""),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Crea un nuevo producto."""
    from decimal import Decimal as D

    stock_value = D(stock) if stock.strip() else None

    producto = Producto(
        empresa_id=current_user.empresa_id,
        nombre=nombre.strip(),
        sku=sku.strip() or None,
        precio_base=D(str(precio_base)),
        unidad_medida=unidad_medida,
        stock=stock_value,
        descripcion=descripcion.strip() or None,
        is_active=True,
    )
    saved = await producto_repo.create(db, producto)
    logger.info("Producto '%s' (#%s) creado por %s #%s", saved.nombre, saved.id, current_user.rol, current_user.id)

    productos = await producto_repo.list_all(db, current_user.empresa_id, include_inactive=True)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_catalogo.html",
        {"user": current_user, "productos": productos, "q": ""},
    )


@router.get("/admin/productos/{producto_id}/editar", response_class=HTMLResponse)
async def editar_producto_form(
    producto_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Muestra formulario para editar un producto."""
    producto = await producto_repo.get_by_id(db, producto_id, current_user.empresa_id)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return templates.TemplateResponse(
        request,
        "admin/partials/producto_form.html",
        {"user": current_user, "producto": producto, "error": None},
    )


@router.post("/admin/productos/{producto_id}/editar", response_class=HTMLResponse)
async def editar_producto_guardar(
    producto_id: int,
    request: Request,
    nombre: str = Form(...),
    sku: str = Form(""),
    precio_base: float = Form(0),
    unidad_medida: str = Form("unidad"),
    stock: str = Form(""),
    descripcion: str = Form(""),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Guarda cambios en un producto."""
    from decimal import Decimal as D

    producto = await producto_repo.get_by_id(db, producto_id, current_user.empresa_id)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    producto.nombre = nombre.strip()
    producto.sku = sku.strip() or None
    producto.precio_base = D(str(precio_base))
    producto.unidad_medida = unidad_medida
    producto.stock = D(stock) if stock.strip() else None
    producto.descripcion = descripcion.strip() or None
    # Promover producto JIT a manual al editarlo — completa sus datos
    if producto.es_automatico:
        producto.es_automatico = False
        logger.info("Producto JIT #%s promovido a manual por %s #%s", producto_id, current_user.rol, current_user.id)

    await db.commit()
    await db.refresh(producto)
    logger.info("Producto #%s editado por %s #%s", producto_id, current_user.rol, current_user.id)

    productos = await producto_repo.list_all(db, current_user.empresa_id, include_inactive=True)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_catalogo.html",
        {"user": current_user, "productos": productos, "q": ""},
    )


@router.post("/admin/productos/{producto_id}/toggle", response_class=HTMLResponse)
async def toggle_producto(
    producto_id: int,
    request: Request,
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Activa o desactiva un producto (soft delete)."""
    producto = await producto_repo.get_by_id(db, producto_id, current_user.empresa_id)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if producto.is_active:
        await producto_repo.deactivate(db, producto_id, current_user.empresa_id)
        logger.info("Producto #%s desactivado por %s #%s", producto_id, current_user.rol, current_user.id)
    else:
        await producto_repo.activate(db, producto_id, current_user.empresa_id)
        logger.info("Producto #%s reactivado por %s #%s", producto_id, current_user.rol, current_user.id)

    productos = await producto_repo.list_all(db, current_user.empresa_id, include_inactive=True)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_catalogo.html",
        {"user": current_user, "productos": productos, "q": ""},
    )


# ==================== FLETEROS ====================


@router.get("/admin/tab/fleteros", response_class=HTMLResponse)
async def tab_fleteros(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """HTMX partial: tab de gestión de fleteros."""
    from app.services.queries.fletero_service import get_fleteros_con_estado

    fleteros = await get_fleteros_con_estado(db, current_user.empresa_id)
    return templates.TemplateResponse(
        request,
        "admin/partials/tab_fleteros.html",
        {"user": current_user, "fleteros": fleteros},
    )


@router.get("/admin/fleteros/nuevo", response_class=HTMLResponse)
async def nuevo_fletero_form(
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
    email: str = Form(""),
    vehiculo: str = Form(""),
    ci: str = Form(""),
    password: str = Form(...),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Crea un nuevo fletero. Owner y Admin. Si se provee email real, se usa; si no, se auto-genera."""
    from app.auth import get_password_hash
    from app.services.queries.fletero_service import get_fleteros_con_estado

    # Determinar email: usar el real si se proveyó, si no auto-generar
    email_provided = email.strip().lower() if email.strip() else ""
    if email_provided:
        # Email real del fletero — permite recuperación de contraseña
        login_email = email_provided
    else:
        # Auto-generar email interno: celular@empresa-slug.fletero
        config = await empresa_repo.get_by_id(db, current_user.empresa_id)
        slug = config.slug if config else f"empresa{current_user.empresa_id}"
        celular_limpio = celular.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        login_email = f"{celular_limpio}@{slug}.fletero"

    # Verificar email duplicado
    existing = await usuario_repo.get_by_email(db, login_email, current_user.empresa_id)
    if existing:
        if email_provided:
            error_msg = f"Ya existe un usuario con el email {login_email}."
        else:
            # Intentar con apellido como fallback para auto-generado
            config = await empresa_repo.get_by_id(db, current_user.empresa_id)
            slug = config.slug if config else f"empresa{current_user.empresa_id}"
            celular_limpio = celular.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            login_email = f"{celular_limpio}.{apellido.strip().lower()}@{slug}.fletero"
            existing = await usuario_repo.get_by_email(db, login_email, current_user.empresa_id)
            if existing:
                error_msg = f"Ya existe un fletero con celular {celular}. Contactá al administrador."
            else:
                # El fallback funcionó, continuamos
                existing = None
        if existing:
            return templates.TemplateResponse(
                request,
                "admin/partials/fletero_form.html",
                {"user": current_user, "fletero_edit": None,
                 "error": error_msg},
            )

    # CI es opcional — el Admin puede crear un fletero sin CI.
    # No aplicamos validación estricta de RUT uruguayo aquí porque:
    # 1) No todos los fleteros tienen CI uruguaya
    # 2) El Admin decide qué datos cargar
    ci_value = ci.strip() if ci.strip() else None

    nuevo = Usuario(
        empresa_id=current_user.empresa_id,
        email=login_email,
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
    logger.info("Fletero '%s %s' creado por owner #%s (email=%s)", nombre, apellido, current_user.id, login_email)

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
    email: str = Form(""),
    vehiculo: str = Form(""),
    ci: str = Form(""),
    current_user: Usuario = Depends(require_role(ROLE_OWNER, ROLE_ADMIN)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Guarda cambios en un fletero. Permite cambiar el email para recuperación de contraseña."""
    from app.services.queries.fletero_service import get_fleteros_con_estado

    fletero = await usuario_repo.get_by_id(db, fletero_id, current_user.empresa_id)
    if fletero is None or fletero.rol != "repartidor":
        raise HTTPException(status_code=404, detail="Fletero no encontrado")

    # Actualizar email si se proporcionó uno nuevo (y es diferente al actual)
    email_provided = email.strip().lower() if email.strip() else ""
    if email_provided and email_provided != fletero.email:
        # Verificar que no exista otro usuario con ese email en la empresa
        existing = await usuario_repo.get_by_email(db, email_provided, current_user.empresa_id)
        if existing and existing.id != fletero_id:
            return templates.TemplateResponse(
                request,
                "admin/partials/fletero_form.html",
                {"user": current_user, "fletero_edit": fletero,
                 "error": f"Ya existe otro usuario con el email {email_provided}."},
            )
        fletero.email = email_provided

    # CI es opcional — el Admin puede dejarlo vacío o cargar cualquier valor
    ci_value = ci.strip() if ci.strip() else None

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